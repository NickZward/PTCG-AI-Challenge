#!/usr/bin/env python3
"""SCALED general-net imitation training — Kaggle GPU version.

Trains the reference transformer at ~3x our laptop size (default 256,8,1024,6,6 ≈ 45M params)
on the all-deck both-seat WINNING-SIDES corpus (~1.2M decisions), with every correction the
project established: next-step action labels, masked softmax CE with TIE-AWARE credit, quality
weighting by pilot winrate, margin-shaped value targets, game-disjoint held-out, and the
random/always-first baselines printed next to every fidelity number.

Self-contained: no game-engine dependency (the corpus is pre-encoded); model dims and decoder
vocab come from the dataset. Checkpoints every epoch to /kaggle/working and RESUMES from the
latest checkpoint automatically, so 12h session limits just mean "run it again".

Expected input dataset layout: /kaggle/input/*/imit_allwins*.npz (+ optional extra .npz corpora).
Outputs in /kaggle/working: big_last.pth, big_best.pth, big_arch.json, log lines in stdout.
"""
import glob
import json
import os
import time

import numpy as np
import torch

# ---------------- config (edit here) ----------------
DIMS = [256, 8, 1024, 6, 6]          # d_model, heads, ffw, enc layers, dec layers
EPOCHS = 30                           # resume-safe; stop the kernel whenever
BS = 192
LR = 2.5e-4
VAL_LAMBDA = 0.4                      # margin blend in the value target
VAL_W = 0.5
HELD_GAMES_FRAC = 0.01
BOOST_PLAYERS = {"dries @ tufa labs": 4.0, "flg": 4.0, "james cox & henry chao": 4.0,
                 "liamk": 3.0, "__taichicchi__": 3.0, "dominic peel": 3.0, "luca": 3.0}
ENCODER_SIZE = 22000
NUM_WORDS_ENCODER = 24
WORK = "/kaggle/working" if os.path.isdir("/kaggle/working") else "."
M_TGT, M_NCAND, M_STYPE, M_TURN, M_WON, M_WR, M_OPP, M_MARGIN, M_PID = range(9)


# ---------------- model (faithful copy of nn_common.MyModel, policy_tanh=False) ----------------
class DecoderLayer(torch.nn.Module):
    def __init__(self, d, h, ff):
        super().__init__()
        self.attention = torch.nn.MultiheadAttention(d, h)
        self.fc1 = torch.nn.Linear(d, ff)
        self.fc2 = torch.nn.Linear(ff, d)
        self.norm1 = torch.nn.LayerNorm(d)
        self.norm2 = torch.nn.LayerNorm(d)

    def forward(self, x, enc):
        y, _ = self.attention(x, enc, enc, need_weights=False)
        res = self.norm1(x + y)
        y = self.fc2(torch.nn.functional.relu(self.fc1(res)))
        return self.norm2(res + y)


class BigModel(torch.nn.Module):
    def __init__(self, d, h, ff, ne, nd, decoder_vocab):
        super().__init__()
        self.d_model = d
        self.encoder_bag = torch.nn.EmbeddingBag(ENCODER_SIZE, d, mode="sum")
        el = torch.nn.TransformerEncoderLayer(d, h, ff, 0)
        self.encoder = torch.nn.TransformerEncoder(el, ne, enable_nested_tensor=False)
        self.encoder_fc = torch.nn.Linear(d, 1)
        self.decoder_bag = torch.nn.EmbeddingBag(decoder_vocab, d, mode="sum")
        self.decoder = torch.nn.ModuleList(DecoderLayer(d, h, ff) for _ in range(nd))
        self.decoder_fc = torch.nn.Linear(d, 1)

    def forward(self, ie, ve, oe, idd, vd, od):
        v = self.encoder_bag(ie, oe, ve).reshape(-1, NUM_WORDS_ENCODER, self.d_model).transpose(0, 1)
        b = v.size(1)
        enc = self.encoder(v)
        val = torch.tanh(self.encoder_fc(enc).mean(0))
        p = self.decoder_bag(idd, od, vd).reshape(b, -1, self.d_model).transpose(0, 1)
        for layer in self.decoder:
            p = layer(p, enc)
        return val, self.decoder_fc(p).transpose(0, 1).reshape(b, -1)


# ---------------- ragged data ----------------
class Ragged:
    def __init__(self, z, tag):
        self.index = z[f"{tag}_index"]; self.value = z[f"{tag}_value"]
        self.wend = z[f"{tag}_wordend"]; self.nwords = z[f"{tag}_nwords"]
        self.tokstart = z[f"{tag}_tokstart"]
        self.wstart = np.concatenate([[0], self.wend[:-1]]).astype(np.int64)

    def shift(self, o):
        self.tokstart = np.concatenate([self.tokstart, o.tokstart + len(self.wend)])
        self.wstart = np.concatenate([self.wstart, o.wstart + len(self.index)])
        self.wend = np.concatenate([self.wend, o.wend + len(self.index)])
        self.index = np.concatenate([self.index, o.index])
        self.value = np.concatenate([self.value, o.value])
        self.nwords = np.concatenate([self.nwords, o.nwords])


def _rar(starts, lens):
    t = int(lens.sum())
    if t == 0:
        return np.zeros(0, np.int64)
    c = np.concatenate([[0], np.cumsum(lens)[:-1]])
    return np.repeat(starts - c, lens) + np.arange(t)


def collate(r, ids, pad_to=None):
    nw = r.nwords[ids].astype(np.int64)
    wid = _rar(r.tokstart[ids], nw)
    lens = (r.wend[wid] - r.wstart[wid]).astype(np.int64)
    flat = _rar(r.wstart[wid], lens)
    idx, val = r.index[flat], r.value[flat]
    if pad_to is None:
        off = np.concatenate([[0], np.cumsum(lens)[:-1]])
        return idx, val, off.astype(np.int64)
    B = len(ids)
    off = np.zeros(B * pad_to, np.int64)
    ends = np.cumsum(lens); starts = np.concatenate([[0], ends[:-1]])
    pos = row_end = 0
    for b in range(B):
        n = int(nw[b]); base = b * pad_to
        off[base:base + n] = starts[pos:pos + n]
        row_end = int(ends[pos + n - 1]) if n else row_end
        off[base + n:base + pad_to] = row_end
        pos += n
    return idx, val, off


def main():
    paths = (sorted(glob.glob("/kaggle/input/**/*.npz", recursive=True))
             or sorted(glob.glob("data/*.npz")))
    if not paths:
        raise SystemExit("NO CORPORA FOUND under /kaggle/input — is the dataset attached and processed?")
    print("corpora:", paths, flush=True)
    enc = dec = None
    metas = []
    players_all = []
    dvocab = None
    for p in paths:
        z = np.load(p, allow_pickle=True)
        if dvocab is None:
            dvocab = int(z["decoder_vocab"][0]) if "decoder_vocab" in z.files else 73847
        e, d = Ragged(z, "enc"), Ragged(z, "dec")
        if enc is None:
            enc, dec = e, d
        else:
            enc.shift(e); dec.shift(d)
        m = z["meta"].copy()
        local = [str(x) for x in z["players"]]
        base = len(players_all)
        m[:, M_PID] = m[:, M_PID] + base
        players_all += local
        metas.append(m)
        print(f"  +{os.path.basename(p)}: {len(m)}", flush=True)
    meta = np.concatenate(metas)
    n = len(meta)
    keep = meta[:, M_NCAND] >= 2
    ids_all = np.nonzero(keep)[0]
    print(f"{n} decisions -> {len(ids_all)} usable | decoder vocab {dvocab}", flush=True)

    # game-disjoint held-out (turn-reset boundaries)
    key = np.stack([meta[:, M_WON], meta[:, M_WR], meta[:, M_OPP], meta[:, M_PID]], 1)
    ng_mask = np.ones(n, bool)
    ng_mask[1:] = (meta[1:, M_TURN] < meta[:-1, M_TURN]) | (key[1:] != key[:-1]).any(1)
    gid = np.cumsum(ng_mask) - 1
    ngames = int(gid[-1]) + 1
    rng = np.random.default_rng(0)
    held_g = np.zeros(ngames, bool)
    held_g[rng.permutation(ngames)[:int(ngames * HELD_GAMES_FRAC)]] = True
    in_held = held_g[gid]
    held = ids_all[in_held[ids_all]]
    train = ids_all[~in_held[ids_all]]
    t_h, c_h = meta[held, M_TGT], meta[held, M_NCAND]
    print(f"{ngames} games; train {len(train)} / held {len(held)} | baselines: "
          f"random {float((1.0/c_h).mean()):.1%} always-0 {float((t_h==0).mean()):.1%}", flush=True)

    # weights: quality by winrate, losses halved (all rows are wins here), named-teacher boosts
    wr = meta[:, M_WR]
    W = np.clip((wr - 0.48) / 0.12, 0.15, 1.6)
    lowered = {k: v for k, v in ((p.lower(), i) for i, p in enumerate(players_all))}
    for nm, b in BOOST_PLAYERS.items():
        pid = lowered.get(nm)
        if pid is not None:
            W = np.where(meta[:, M_PID].astype(int) == pid, W * b, W)
    W = W.astype(np.float32)

    # tie mask (cached)
    tm_path = os.path.join(WORK, "tiemask.npy")
    if os.path.exists(tm_path):
        TIE = np.load(tm_path)
    else:
        print("hashing tie groups...", flush=True)
        TIE = np.zeros(int(dec.nwords.sum()), bool)
        pos = 0
        for s in range(n):
            k = int(dec.nwords[s]); w0 = int(dec.tokstart[s]); t = int(meta[s, M_TGT])
            hs = [hash(bytes(dec.index[dec.wstart[w0+j]:dec.wend[w0+j]]) +
                       bytes(dec.value[dec.wstart[w0+j]:dec.wend[w0+j]])) for j in range(k)]
            for j in range(k):
                TIE[pos + j] = hs[j] == hs[t]
            pos += k
        np.save(tm_path, TIE)
    cand_off = np.concatenate([[0], np.cumsum(dec.nwords)]).astype(np.int64)

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    if dev.type == "cuda" and torch.cuda.get_device_capability()[0] < 7:
        print("P100/sm60 unsupported by this torch — CPU fallback (slow!)", flush=True)
        dev = torch.device("cpu")
    model = BigModel(*DIMS, dvocab).to(dev)
    print(f"device {dev} | params {sum(p.numel() for p in model.parameters()):,}", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=1e-2)
    scaler = torch.cuda.amp.GradScaler(enabled=dev.type == "cuda")
    start_ep, best = 0, 0.0
    last = os.path.join(WORK, "big_last.pth")
    if not os.path.exists(last):
        # cross-session resume: prior version's output mounts under /kaggle/input via
        # kernel_sources — copy its checkpoint (and tie-mask cache) into the fresh working dir
        import shutil
        for src in glob.glob("/kaggle/input/**/big_last.pth", recursive=True):
            shutil.copy(src, last)
            print(f"resume checkpoint pulled from {src}", flush=True)
            break
        if not os.path.exists(tm_path):
            for src in glob.glob("/kaggle/input/**/tiemask.npy", recursive=True):
                shutil.copy(src, tm_path)
                break
    if os.path.exists(last):
        ck = torch.load(last, map_location="cpu")
        model.load_state_dict(ck["model"]); opt.load_state_dict(ck["opt"])
        start_ep, best = ck["epoch"] + 1, ck.get("best", 0.0)
        model = model.to(dev)
        print(f"RESUMED at epoch {start_ep} (best {best:.3f})", flush=True)

    def tie_mask_for(ids, maxc):
        m = np.zeros((len(ids), maxc), bool)
        for b, s in enumerate(ids):
            m[b, :int(meta[s, M_NCAND])] = TIE[cand_off[s]:cand_off[s + 1]]
        return torch.as_tensor(m, device=dev)

    def forward(ids):
        maxc = int(meta[ids, M_NCAND].max())
        ie, ve, oe = collate(enc, ids)
        di, dv, do = collate(dec, ids, pad_to=maxc)
        v, p = model(torch.as_tensor(ie, dtype=torch.int32, device=dev),
                     torch.as_tensor(ve, dtype=torch.float32, device=dev),
                     torch.as_tensor(oe, dtype=torch.int32, device=dev),
                     torch.as_tensor(di, dtype=torch.int32, device=dev),
                     torch.as_tensor(dv, dtype=torch.float32, device=dev),
                     torch.as_tensor(do, dtype=torch.int32, device=dev))
        return v, p, maxc

    @torch.inference_mode()
    def fidelity(chunk=384):
        model.eval()
        h1 = h3 = 0
        for i in range(0, len(held), chunk):
            b = held[i:i + chunk]
            b = b[np.argsort(meta[b, M_NCAND])]
            _, p, maxc = forward(b)
            nc = torch.as_tensor(meta[b, M_NCAND], dtype=torch.long, device=dev)
            ok = tie_mask_for(b, maxc)
            p = p.masked_fill(torch.arange(maxc, device=dev)[None, :] >= nc[:, None], float("-inf"))
            top = p.topk(min(3, maxc), 1).indices
            h1 += int(ok.gather(1, top[:, :1]).squeeze(1).sum())
            h3 += int(ok.gather(1, top).any(1).sum())
        model.train()
        return h1 / len(held), h3 / len(held)

    ids = train.copy()
    for ep in range(start_ep, EPOCHS):
        t0 = time.time()
        rng.shuffle(ids)
        nb = len(ids) // BS
        tot = 0.0
        for i in range(nb):
            b = ids[i * BS:(i + 1) * BS]
            b = b[np.argsort(meta[b, M_NCAND])]
            opt.zero_grad(set_to_none=True)
            with torch.autocast(device_type=dev.type, enabled=dev.type == "cuda"):
                v, p, maxc = forward(b)
                nc = torch.as_tensor(meta[b, M_NCAND], dtype=torch.long, device=dev)
                valid = torch.arange(maxc, device=dev)[None, :] < nc[:, None]
                win = np.where(meta[b, M_WON] > 0.5, 1.0, -1.0)
                marg = np.clip(meta[b, M_MARGIN] * 2.0, -1.0, 1.0)
                vt = torch.as_tensor((1 - VAL_LAMBDA) * win + VAL_LAMBDA * marg,
                                     dtype=torch.float32, device=dev)[:, None]
                lv = torch.nn.functional.huber_loss(v.float(), vt, delta=0.5)
                logp = torch.log_softmax(p.float().masked_fill(~valid, float("-inf")), 1)
                ok = tie_mask_for(b, maxc)
                lp = -torch.logsumexp(logp.masked_fill(~ok, float("-inf")), 1)
                w = torch.as_tensor(W[b], dtype=torch.float32, device=dev)
                loss = (lp * w).mean() + VAL_W * lv
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            scaler.step(opt)
            scaler.update()
            tot += float(loss.detach())
            if i % 500 == 0 and i:
                print(f"  ep{ep} {i}/{nb} loss {tot/(i+1):.4f} ({time.time()-t0:.0f}s)", flush=True)
        a1, a3 = fidelity()
        print(f"EPOCH {ep}: loss {tot/max(1,nb):.4f}  top1 {a1:.1%} top3 {a3:.1%}  "
              f"{time.time()-t0:.0f}s", flush=True)
        torch.save({"model": model.state_dict(), "opt": opt.state_dict(),
                    "epoch": ep, "best": best}, last)
        if a1 > best:
            best = a1
            torch.save(model.state_dict(), os.path.join(WORK, "big_best.pth"))
            json.dump({"model": DIMS, "policy_tanh": False, "decoder_vocab": dvocab, "feat": 2},
                      open(os.path.join(WORK, "big_arch.json"), "w"))
            print(f"  -> best saved ({best:.1%})", flush=True)


if __name__ == "__main__":
    main()
