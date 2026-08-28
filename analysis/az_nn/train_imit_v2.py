#!/usr/bin/env python3
"""Imitation trainer v2 — the corrected objective.

WHY THIS EXISTS
The v1 run (train_core._train_epoch) trained the policy head as REGRESSION: tanh output, targets
+1 for the expert's action and -1 for every other candidate, HuberLoss(delta=0.1) summed over 64
padded slots. Three things go wrong at once:
  * Huber caps the per-slot gradient at delta (0.1) no matter how wrong the prediction is, so the
    single +1 target contributes ~1/N of the batch's policy gradient and the N-1 negatives dominate;
    the model's cheapest win is "output -1 everywhere".
  * tanh saturates, killing what gradient is left.
  * Nothing normalises across candidates, so the net never has to learn a RELATIVE ranking — which
    is the only thing top-1 accuracy measures.
Measured consequence: v1 reached 29% top-1 on MAIN decisions where "always pick candidate 0" scores
34.5% and uniform-random scores 19.4%. It had learned almost nothing.

v2 trains the policy head as what it is: a classifier over the legal candidate set.
  * raw logits (policy_tanh=False) + masked softmax CROSS-ENTROPY against the expert's index
  * value head kept, separately weighted (it is not the point of an imitation run)
  * per-sample weights so we imitate STRONG play (see --min-wr / --wins-only / --weight)
  * all select types (v1 was MAIN-only), with per-type fidelity reported

Usage:
  train_imit_v2.py <data.npz>[,<data2.npz>] [--out=NAME] [--epochs=12] [--bs=128] [--lr=3e-4]
                   [--model=128,8,512,4,4] [--min-wr=0.0] [--wins-only] [--main-only]
                   [--weight=none|quality] [--held=5000] [--device=mps|cpu] [--legacy-loss]
`--legacy-loss` reproduces the v1 objective for a controlled A/B.
"""
import json
import os
import sys
import time

import numpy as np
import torch

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
import nn_common as NN  # noqa: E402

M_TGT, M_NCAND, M_STYPE, M_TURN, M_WON, M_WR, M_OPP, M_MARGIN, M_PID = range(9)
M_PDIFF = 9   # current prize diff at decision (10-col corpora only)
M_CLOSE = 10  # expert ENDED the turn or ATTACKED here (11-col corpora only)


# ----------------------------------------------------------------------------------------
# ragged storage -> batched EmbeddingBag input, fully vectorised
# ----------------------------------------------------------------------------------------
class Ragged:
    def __init__(self, npz, tag):
        self.index = npz[f"{tag}_index"]
        self.value = npz[f"{tag}_value"]
        self.wend = npz[f"{tag}_wordend"]
        self.nwords = npz[f"{tag}_nwords"]
        self.tokstart = npz[f"{tag}_tokstart"]
        self.wstart = np.concatenate([[0], self.wend[:-1]]).astype(np.int64)

    def shift(self, other):
        """Concatenate another Ragged onto this one (multi-file corpora)."""
        self.tokstart = np.concatenate([self.tokstart, other.tokstart + len(self.wend)])
        self.wstart = np.concatenate([self.wstart, other.wstart + len(self.index)])
        self.wend = np.concatenate([self.wend, other.wend + len(self.index)])
        self.index = np.concatenate([self.index, other.index])
        self.value = np.concatenate([self.value, other.value])
        self.nwords = np.concatenate([self.nwords, other.nwords])


def _ragged_arange(starts, lens):
    """Concatenated [s, s+l) ranges, vectorised."""
    total = int(lens.sum())
    if total == 0:
        return np.zeros(0, dtype=np.int64)
    csum = np.concatenate([[0], np.cumsum(lens)[:-1]])
    return np.repeat(starts - csum, lens) + np.arange(total)


def collate(rag, ids, pad_to=None):
    """Build (index, value, offsets) for a batch. pad_to=None -> use each sample's own word count;
    otherwise pad every sample to `pad_to` words with EMPTY bags (needed for the decoder, whose
    candidate count varies per sample but must be rectangular for the model reshape)."""
    nw = rag.nwords[ids].astype(np.int64)
    word_ids = _ragged_arange(rag.tokstart[ids], nw)
    lens = (rag.wend[word_ids] - rag.wstart[word_ids]).astype(np.int64)
    flat = _ragged_arange(rag.wstart[word_ids], lens)
    index = rag.index[flat]
    value = rag.value[flat]

    if pad_to is None:
        offsets = np.concatenate([[0], np.cumsum(lens)[:-1]])
        return index, value, offsets.astype(np.int64)

    # rectangular: real words first, then empty bags to `pad_to`
    B = len(ids)
    offsets = np.zeros(B * pad_to, dtype=np.int64)
    ends = np.cumsum(lens)
    starts = np.concatenate([[0], ends[:-1]])
    pos = 0
    row_end = 0
    for b in range(B):
        n = int(nw[b])
        base = b * pad_to
        offsets[base:base + n] = starts[pos:pos + n]
        row_end = int(ends[pos + n - 1]) if n else row_end
        offsets[base + n:base + pad_to] = row_end
        pos += n
    return index, value, offsets


# ----------------------------------------------------------------------------------------
def load(paths):
    """Concatenate corpora. Player ids are per-file, so remap into one global namespace —
    otherwise a --boost-players name match in file A silently boosts an unrelated pid in file B."""
    encs, decs, metas = None, None, []
    global_players = {}
    for p in paths:
        z = np.load(p, allow_pickle=True)
        e, d = Ragged(z, "enc"), Ragged(z, "dec")
        if encs is None:
            encs, decs = e, d
        else:
            encs.shift(e)
            decs.shift(d)
        m = z["meta"].copy()
        local = [str(x) for x in z["players"]]
        remap = np.asarray([global_players.setdefault(nm, len(global_players)) for nm in local])
        m[:, M_PID] = remap[m[:, M_PID].astype(int)]
        metas.append(m)
        print(f"  + {os.path.basename(p)}: {len(m)} decisions, players {local[:5]}"
              f"{'...' if len(local) > 5 else ''}", flush=True)
    players = [nm for nm, _ in sorted(global_players.items(), key=lambda kv: kv[1])]
    return encs, decs, np.concatenate(metas), players


def tie_groups(dec, meta, cache_path=None):
    """Per-candidate 'counts as correct' mask, flat over sum(ncand).

    Measured on this corpus: 60.7% of decisions contain >=2 candidates whose decoder token-bags
    are BYTE-IDENTICAL — the model cannot distinguish them, so demanding the expert's exact combo
    (and punishing its twin) injects contradictory gradients and caps content-only top-1 at ~80%.
    A candidate is credited iff its (index,value) bag hashes equal to the expert target's bag.
    """
    if cache_path and os.path.exists(cache_path):
        m = np.load(cache_path)
        if len(m) == int(dec.nwords.sum()):
            return m
    correct = np.zeros(int(dec.nwords.sum()), dtype=bool)
    idx, val = dec.index, dec.value
    ws, we = dec.wstart, dec.wend
    pos = 0
    for s in range(len(dec.nwords)):
        n = int(dec.nwords[s])
        t = int(meta[s, M_TGT])
        w0 = int(dec.tokstart[s])
        hs = [hash(bytes(idx[ws[w0 + k]:we[w0 + k]]) + bytes(val[ws[w0 + k]:we[w0 + k]]))
              for k in range(n)]
        ht = hs[t]
        for k in range(n):
            correct[pos + k] = (hs[k] == ht)
        pos += n
        if s % 200000 == 0 and s:
            print(f"  tie-hash {s}/{len(dec.nwords)}", flush=True)
    if cache_path:
        np.save(cache_path, correct)
    return correct


def sample_weights(meta, mode, boost_pids=None, boost=2.5, early_boost=1.0,
                   opp_boost_idx=None, opp_boost=1.0, behind_mirror_boost=1.0,
                   close_boost=1.0):
    if mode == "none":
        w = np.ones(len(meta), dtype=np.float32)
    else:
        # quality: scale with how far above 50% the pilot is, halve decisions from lost games
        wr = meta[:, M_WR]
        w = np.clip((wr - 0.48) / 0.12, 0.15, 1.6)
        w = np.where(meta[:, M_WON] > 0.5, w, w * 0.35)
    if boost_pids:
        # upweight named players (e.g. the ladder-proven top 3) over the rest of the corpus
        w = np.where(np.isin(meta[:, M_PID].astype(int), list(boost_pids)), w * boost, w)
    if behind_mirror_boost != 1.0 and meta.shape[1] > M_PDIFF and opp_boost_idx is not None:
        # SITUATIONAL slice (v16): decisions IN THE MIRROR while BEHIND on prizes. Measured:
        # our mirror-comeback win rate after conceding first prize = 23% vs the #1's 62%,
        # while mirror conversion/tempo are already expert-level. Minority slice + measured
        # deficit = the pattern that worked (v14) rather than the one that failed (v15).
        mask = (meta[:, M_OPP].astype(int) == opp_boost_idx) & (meta[:, M_PDIFF] < 0)
        print(f"  behind-mirror slice: {int(mask.sum())} decisions "
              f"({mask.mean():.1%}) x{behind_mirror_boost}", flush=True)
        w = np.where(mask, w * behind_mirror_boost, w)
    if opp_boost_idx is not None and opp_boost != 1.0:
        # MATCHUP-TARGETED weighting (2026-07-29): the mirror is 32% of the 1000+ field and our
        # weakest big cell (42%). Upweight decisions made AGAINST the given archetype so the
        # objective concentrates on that matchup (multiplies with player boosts: the #1 players'
        # mirror games carry the most weight — exactly the play we want).
        w = np.where(meta[:, M_OPP].astype(int) == opp_boost_idx, w * opp_boost, w)
    if early_boost and early_boost != 1.0:
        # PHASE-TARGETED weighting (2026-07-29): measured tempo gap — we take 1.31 prizes by T8
        # vs the #1-class players' 1.61-1.68 with EQUAL board development, i.e. early conversion
        # is the last measured behavioural deficit. Upweight turn<=8 decisions so the imitation
        # objective concentrates where the gap lives.
        w = np.where(meta[:, M_TURN] <= 8.0, w * early_boost, w)
    if close_boost != 1.0 and meta.shape[1] > M_CLOSE:
        # ACTION-TARGETED weighting (2026-08-12): both imitation agents systematically REFUSE to
        # close the turn. Measured on held-out pro games: palsystem picks END 139x where our top-1
        # picks it 46x (3.0x gap); Dipam terminates his turn at 485 decisions and drag_pol keeps
        # spending at 228 of them (47%), walking past Phantom Dive 73x and END 71x. We over-develop
        # and dump the hand instead of swinging. This is a MINORITY slice (~7% of decisions) with a
        # large MEASURED deficit — the v14 pattern that worked, not the v15 pattern that failed
        # (v15 boosted the mirror, already 43% of the corpus, and bought nothing).
        mask = meta[:, M_CLOSE] > 0.5
        print(f"  turn-CLOSING slice: {int(mask.sum())} decisions "
              f"({mask.mean():.1%}) x{close_boost}", flush=True)
        w = np.where(mask, w * close_boost, w)
    return w.astype(np.float32)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    F = {a.split("=")[0].lstrip("-"): (a.split("=", 1)[1] if "=" in a else "1")
         for a in sys.argv[1:] if a.startswith("--")}
    paths = args[0].split(",")
    name = F.get("out", "grimm_imit_v2")
    epochs = int(F.get("epochs", 12))
    bs = int(F.get("bs", 128))
    lr = float(F.get("lr", 3e-4))
    dims = [int(x) for x in F.get("model", "128,8,512,4,4").split(",")]
    min_wr = float(F.get("min-wr", 0.0))
    wins_only = "wins-only" in F
    main_only = "main-only" in F
    wmode = F.get("weight", "quality")
    nheld = int(F.get("held", 5000))
    legacy = "legacy-loss" in F
    val_w = float(F.get("value-weight", 0.3))
    val_lambda = float(F.get("value-lambda", 0.0))   # 0 = pure win/loss (old); >0 blends margin

    print(f"loading {paths}", flush=True)
    enc, dec, meta, all_players = load(paths)
    z0 = np.load(paths[0], allow_pickle=True)
    feat = int(z0["feat"][0]) if "feat" in z0.files else 1
    dvocab = int(z0["decoder_vocab"][0]) if "decoder_vocab" in z0.files else NN.decoder_size
    print(f"decoder feat={feat} vocab={dvocab}", flush=True)
    n0 = len(meta)

    keep = np.ones(n0, dtype=bool)
    if min_wr > 0:
        keep &= meta[:, M_WR] >= min_wr
    if wins_only:
        keep &= meta[:, M_WON] > 0.5
    if main_only:
        keep &= meta[:, M_STYPE] == 0
    keep &= meta[:, M_NCAND] >= 2          # nothing to learn from a forced move
    ids_all = np.nonzero(keep)[0]
    print(f"{n0} decisions -> {len(ids_all)} after filter "
          f"(min_wr={min_wr} wins_only={wins_only} main_only={main_only})", flush=True)

    # ---- HELD-OUT SPLIT BY GAME, not by decision ------------------------------------------
    # Decisions are written game-by-game, so a game's decisions are contiguous. A random
    # per-decision split would put ~40 near-duplicate states from the same game on both sides and
    # inflate fidelity. Recover game boundaries: the turn counter is non-decreasing within a game
    # and resets at the next one, and (won, winrate, opp deck, player) are constant within a game.
    key = np.stack([meta[:, M_WON], meta[:, M_WR], meta[:, M_OPP], meta[:, M_PID]], 1)
    newgame = np.ones(len(meta), dtype=bool)
    newgame[1:] = (meta[1:, M_TURN] < meta[:-1, M_TURN]) | (key[1:] != key[:-1]).any(1)
    gid = np.cumsum(newgame) - 1
    ngames = int(gid[-1]) + 1
    rng = np.random.default_rng(0)
    gperm = rng.permutation(ngames)
    held_g = np.zeros(ngames, dtype=bool)
    # take whole games until the held-out decision budget is met
    counts = np.bincount(gid, minlength=ngames)
    acc = 0
    for g in gperm:
        if acc >= nheld:
            break
        held_g[g] = True
        acc += counts[g]
    in_held = held_g[gid]
    held = ids_all[in_held[ids_all]]
    train = ids_all[~in_held[ids_all]]
    print(f"{ngames} games detected -> held-out {int(held_g.sum())} games / {len(held)} decisions "
          f"(disjoint from the {len(train)} training decisions)", flush=True)
    boost_pids = None
    if "boost-players" in F:
        want = [s.strip() for s in F["boost-players"].split(",")]
        boost_pids = {i for i, p in enumerate(all_players) if str(p) in want}
        print(f"boosting players {want} -> pids {sorted(boost_pids)} "
              f"x{float(F.get('boost', 2.5))}", flush=True)
    opp_boost_idx = None
    if "boost-opp" in F:
        vocab = [str(x) for x in np.load(paths[0], allow_pickle=True)["deck_vocab"]]
        want_opp = F["boost-opp"]
        if want_opp in vocab:
            opp_boost_idx = vocab.index(want_opp)
            print(f"boosting decisions vs {want_opp} (idx {opp_boost_idx}) "
                  f"x{float(F.get('opp-boost', 3.0))}", flush=True)
    W = sample_weights(meta, wmode, boost_pids, float(F.get("boost", 2.5)),
                       float(F.get("boost-early", 1.0)),
                       opp_boost_idx, float(F.get("opp-boost", 3.0)),
                       float(F.get("boost-behind-mirror", 1.0)),
                       float(F.get("boost-close", 1.0)))

    # tie-aware credit: flat per-candidate mask + per-sample offsets into it
    strict = "strict-target" in F
    cand_off = np.concatenate([[0], np.cumsum(dec.nwords)]).astype(np.int64)
    if not strict:
        print("hashing candidate bags for tie groups...", flush=True)
        TIE = tie_groups(dec, meta, cache_path=paths[0] + ".tiemask.npy")
        n_tied = int(TIE.sum()) - len(meta)
        print(f"tie mask ready: {n_tied} extra credited candidates "
              f"({n_tied / max(1, len(meta)):.2f}/decision)", flush=True)
    else:
        TIE = None

    # ---- baselines the model must beat to have learned anything ----
    def baselines(ids, label):
        t, c = meta[ids, M_TGT], meta[ids, M_NCAND]
        print(f"  [{label}] n={len(ids)}  random={float((1.0 / c).mean()):.1%}  "
              f"always-0={float((t == 0).mean()):.1%}", flush=True)
    baselines(held, "held-out baselines")

    torch.manual_seed(0)   # audit 2026-08-12: model init/dropout were unseeded — held-out
    # fidelity and the saved best checkpoint varied run-to-run while we compared runs at ±1pp
    dev = torch.device(F.get("device", "mps" if torch.backends.mps.is_available() else "cpu"))
    model = NN.MyModel(*dims, policy_tanh=legacy, decoder_vocab=dvocab).to(dev)
    if "init" in F:
        # warm-start fine-tuning from an existing checkpoint (same arch required)
        model.load_state_dict(torch.load(F["init"], map_location="cpu"))
        model = model.to(dev)
        print(f"initialized from {F['init']}", flush=True)
    print(f"device={dev}  params={sum(p.numel() for p in model.parameters()):,}  "
          f"objective={'LEGACY huber+-1' if legacy else 'softmax CE'}", flush=True)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    sched = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=lr, total_steps=max(1, epochs * (len(train) // bs)), pct_start=0.15)

    def forward(ids):
        maxc = int(meta[ids, M_NCAND].max())
        ei, ev, eo = collate(enc, ids)
        di, dv, do = collate(dec, ids, pad_to=maxc)
        out = model(
            torch.as_tensor(ei, dtype=torch.int32, device=dev),
            torch.as_tensor(ev, dtype=torch.float32, device=dev),
            torch.as_tensor(eo, dtype=torch.int32, device=dev),
            torch.as_tensor(di, dtype=torch.int32, device=dev),
            torch.as_tensor(dv, dtype=torch.float32, device=dev),
            torch.as_tensor(do, dtype=torch.int32, device=dev))
        return out[0], out[1], maxc

    def tie_mask_for(ids, maxc):
        """[B, maxc] bool: which candidates count as the expert's move (incl. identical twins)."""
        m = np.zeros((len(ids), maxc), dtype=bool)
        for b, s in enumerate(ids):
            m[b, :int(meta[s, M_NCAND])] = TIE[cand_off[s]:cand_off[s + 1]]
        return torch.as_tensor(m, device=dev)

    def loss_of(ids):
        v, p, maxc = forward(ids)
        nc = torch.as_tensor(meta[ids, M_NCAND], dtype=torch.long, device=dev)
        tgt = torch.as_tensor(meta[ids, M_TGT], dtype=torch.long, device=dev)
        w = torch.as_tensor(W[ids], dtype=torch.float32, device=dev)
        valid = torch.arange(maxc, device=dev)[None, :] < nc[:, None]
        win = np.where(meta[ids, M_WON] > 0.5, 1.0, -1.0)
        if val_lambda > 0:
            # margin-shaped value target (ladder-autopsy fix #1): whole-game +/-1 gives the search
            # no gradient between "barely winning" and "crushing", which is why behind-recovery
            # fails (experts win 57-64% from -1/-2 down, we won 34-41%). Blend in the final prize
            # margin (M_MARGIN in [-1,1], x2 clipped so a 3-prize margin saturates).
            marg = np.clip(meta[ids, M_MARGIN] * 2.0, -1.0, 1.0)
            vt_np = (1.0 - val_lambda) * win + val_lambda * marg
        else:
            vt_np = win
        vt = torch.as_tensor(vt_np, dtype=torch.float32, device=dev)[:, None]
        lv = (torch.nn.functional.huber_loss(v, vt, reduction="none", delta=0.5).squeeze(1) * w).mean()
        if legacy:
            lab = torch.where(
                torch.arange(maxc, device=dev)[None, :] == tgt[:, None], 1.0, -1.0)
            lp = torch.nn.functional.huber_loss(p, lab, reduction="none", delta=0.1)
            lp = (lp * valid).sum(1)
            lp = (lp * w).mean()
        elif TIE is None:
            logits = p.masked_fill(~valid, float("-inf"))
            lp = torch.nn.functional.cross_entropy(logits, tgt, reduction="none")
            lp = (lp * w).mean()
        else:
            # tie-aware CE: -log(sum of probability over the expert's indistinguishable group)
            logits = p.masked_fill(~valid, float("-inf"))
            logp = torch.log_softmax(logits, dim=1)
            ok = tie_mask_for(ids, maxc)
            lp = -torch.logsumexp(logp.masked_fill(~ok, float("-inf")), dim=1)
            lp = (lp * w).mean()
        return lp + val_w * lv, lp.detach(), lv.detach()

    @torch.inference_mode()
    def fidelity(ids, chunk=256):
        """Returns (tie-aware top1, tie-aware top3, strict top1, per-type tie-aware).
        Tie-aware = credit if the argmax candidate is byte-identical to the expert's pick
        (indistinguishable to the model AND to the game up to representation)."""
        model.eval()
        hit1 = hit3 = strict1 = 0
        per_type = {}
        for i in range(0, len(ids), chunk):
            b = ids[i:i + chunk]
            order = np.argsort(meta[b, M_NCAND])       # group similar widths -> less padding
            b = b[order]
            _, p, maxc = forward(b)
            nc = torch.as_tensor(meta[b, M_NCAND], dtype=torch.long, device=dev)
            valid = torch.arange(maxc, device=dev)[None, :] < nc[:, None]
            p = p.masked_fill(~valid, float("-inf"))
            tgt = torch.as_tensor(meta[b, M_TGT], dtype=torch.long, device=dev)
            ok = tie_mask_for(b, maxc) if TIE is not None else \
                torch.nn.functional.one_hot(tgt, maxc).bool()
            top = p.topk(min(3, maxc), dim=1).indices
            c1 = ok.gather(1, top[:, :1]).squeeze(1)
            c3 = ok.gather(1, top).any(1)
            strict1 += int((top[:, 0] == tgt).sum())
            hit1 += int(c1.sum())
            hit3 += int(c3.sum())
            for st, o in zip(meta[b, M_STYPE].astype(int), c1.tolist()):
                a = per_type.setdefault(st, [0, 0])
                a[0] += int(o)
                a[1] += 1
        model.train()
        return hit1 / len(ids), hit3 / len(ids), strict1 / len(ids), per_type

    outdir = os.path.join(ROOT, "model/az")
    best = 0.0
    print(f"\ntrain={len(train)} held={len(held)} epochs={epochs} bs={bs}", flush=True)
    for ep in range(epochs):
        t0 = time.time()
        rng.shuffle(train)
        tot = totp = totv = 0.0
        nb = len(train) // bs
        for i in range(nb):
            b = train[i * bs:(i + 1) * bs]
            b = b[np.argsort(meta[b, M_NCAND])]
            opt.zero_grad(set_to_none=True)
            l, lp, lv = loss_of(b)
            l.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            tot += float(l.detach())
            totp += float(lp)
            totv += float(lv)
            if i % 500 == 0 and i:
                print(f"    ep{ep} {i}/{nb} loss {tot/(i+1):.4f}", flush=True)
        a1, a3, s1, pt = fidelity(held)
        main = pt.get(0, [0, 1])
        types = "  ".join(f"t{k}:{v[0]/v[1]:.0%}({v[1]})" for k, v in sorted(pt.items()) if v[1] >= 20)
        print(f"epoch {ep}: loss {tot/nb:.4f} (pol {totp/nb:.4f} val {totv/nb:.4f})  "
              f"MAIN-top1 {main[0]/main[1]:.1%}  all-top1 {a1:.1%} (strict {s1:.1%})  "
              f"top3 {a3:.1%}  {time.time()-t0:.0f}s\n    {types}", flush=True)
        if a1 > best:
            best = a1
            torch.save(model.state_dict(), os.path.join(outdir, f"{name}_best.pth"))
            json.dump({"model": dims, "policy_tanh": legacy, "feat": feat,
                       "decoder_vocab": dvocab},
                      open(os.path.join(outdir, f"{name}_arch.json"), "w"))
    print(f"\nBEST held-out top1: {best:.1%}  -> model/az/{name}_best.pth")


if __name__ == "__main__":
    main()
