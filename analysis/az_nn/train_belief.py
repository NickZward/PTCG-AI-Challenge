#!/usr/bin/env python3
"""Belief-model trainer v0 — predict the opponent's hidden hand (count vector over card vocab)
from the acting seat's MASKED observation.

Model: the pretrained grimm_imit_v11 ENCODER tower (EmbeddingBag + 4-layer Transformer over the
24 state words, d=128) with a fresh Linear(128 -> vocab) head on the mean-pooled encoder output.
The head emits LOG-RATES and the loss is Poisson NLL on copy-counts. Poisson over MSE because
targets are small counts (0..4 copies, ~7 nonzero cells of ~300): exp(out) is a calibrated
expected-copies estimate usable directly as search fill-in weights, the implied presence prob
1-exp(-lambda) is monotone in the logit (so AUC ranking is unaffected), and MSE on 97%-zero
cells underweights exactly the rare tech cards a belief model exists to catch.

Eval (held-out 10% of GAMES, disjoint):
  (a) per-card presence AUC, macro over cards with >=100 held-out positives;
  (b) top-H multiset overlap where H = true handCount (greedy allocation on expected counts);
  both vs the ARCHETYPE-AVERAGE baseline: mean train-split hand-count vector of the opponent's
  true archetype at min(turn,12), with arch-overall and global fallbacks. The baseline KNOWS the
  true archetype, which the net must infer from the board — beating it is the headline.

Usage: KMP_DUPLICATE_LIB_OK=TRUE train_belief.py <data.npz> <out.pth>
         [--epochs=3] [--bs=512] [--lr-head=1e-3] [--lr-enc=1e-4] [--seed=0] [--freeze-enc]
"""
import json
import os
import sys

import numpy as np

ROOT = "/Users/nickzwart/Desktop/PTCG-AI-Challenge"
sys.path.insert(0, os.path.join(ROOT, "my-agent/grimmsnarl_v17"))
sys.path.insert(0, os.path.join(ROOT, "analysis/az_nn"))
import torch  # noqa: E402
import nn_common as NN  # noqa: E402

DATA = sys.argv[1]
OUT = sys.argv[2]
F = {a.split("=")[0].lstrip("-"): (a.split("=", 1)[1] if "=" in a else True)
     for a in sys.argv[3:]}
EPOCHS = int(F.get("epochs", 3))
BS = int(F.get("bs", 512))
LR_HEAD = float(F.get("lr-head", 1e-3))
LR_ENC = float(F.get("lr-enc", 1e-4))
SEED = int(F.get("seed", 0))
FREEZE = bool(F.get("freeze-enc", False))
INIT = os.path.join(ROOT, "model/az/grimm_imit_v11_best.pth")

M_GAME, M_SEAT, M_STEP, M_TURN, M_ARCH, M_HCNT, M_STYPE = range(7)


# ---- ragged storage -> EmbeddingBag input (copied from train_imit_v2) ----
class Ragged:
    def __init__(self, npz, tag):
        self.index = npz[f"{tag}_index"]; self.value = npz[f"{tag}_value"]
        self.wend = npz[f"{tag}_wordend"]; self.nwords = npz[f"{tag}_nwords"]
        self.tokstart = npz[f"{tag}_tokstart"]
        self.wstart = np.concatenate([[0], self.wend[:-1]]).astype(np.int64)


def _ragged_arange(starts, lens):
    total = int(lens.sum())
    if total == 0:
        return np.zeros(0, dtype=np.int64)
    csum = np.concatenate([[0], np.cumsum(lens)[:-1]])
    return np.repeat(starts - csum, lens) + np.arange(total)


def collate(rag, ids):
    nw = rag.nwords[ids].astype(np.int64)
    word_ids = _ragged_arange(rag.tokstart[ids], nw)
    lens = (rag.wend[word_ids] - rag.wstart[word_ids]).astype(np.int64)
    flat = _ragged_arange(rag.wstart[word_ids], lens)
    offsets = np.concatenate([[0], np.cumsum(lens)[:-1]])
    return rag.index[flat], rag.value[flat], offsets.astype(np.int64)


class BeliefNet(torch.nn.Module):
    """Pretrained MyModel encoder tower + fresh hand-count head (log-rates)."""

    def __init__(self, base, vocab_n):
        super().__init__()
        self.encoder_bag = base.encoder_bag
        self.encoder = base.encoder
        self.d_model = base.d_model
        self.head = torch.nn.Linear(base.d_model, vocab_n)

    def forward(self, index, value, offsets):
        v = self.encoder_bag(index, offsets, value)
        v = v.reshape(-1, NN.num_words_encoder, self.d_model).transpose(0, 1)
        e = self.encoder(v)            # [24, B, d]
        return self.head(e.mean(0))    # [B, vocab] log-rates


def presence_auc(scores, labels):
    """AUC via average ranks (tie-corrected), no scipy."""
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty(len(scores))
    sv = scores[order]
    i = 0
    r = 1
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        ranks[order[i:j + 1]] = (r + r + (j - i)) / 2.0
        r += j - i + 1
        i = j + 1
    pos = labels > 0
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return None
    return (ranks[pos].sum() - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def topH_overlap(scores, tgt, hcnt):
    """Greedy expected-count allocation: repeatedly take best remaining copy."""
    out = np.zeros(len(tgt))
    for r in range(len(tgt)):
        p = scores[r].astype(np.float64).copy()
        H = int(hcnt[r])
        pred = np.zeros(len(p), dtype=np.int32)
        for _ in range(H):
            j = int(np.argmax(p))
            pred[j] += 1
            p[j] -= 1.0
        out[r] = np.minimum(pred, tgt[r]).sum() / max(1, H)
    return out


def report(name, scores, tgt, meta, min_pos=100):
    """Macro presence-AUC + top-H overlap, overall and per phase."""
    res = {}
    for label, mask in [("all", np.ones(len(meta), bool)),
                        ("T1-6", meta[:, M_TURN] <= 6), ("T7+", meta[:, M_TURN] >= 7)]:
        sc, tg, mt = scores[mask], tgt[mask], meta[mask]
        aucs = []
        for c in range(tgt.shape[1]):
            if int((tg[:, c] > 0).sum()) < min_pos:
                continue
            a = presence_auc(sc[:, c], tg[:, c])
            if a is not None:
                aucs.append(a)
        ov = topH_overlap(sc, tg, mt[:, M_HCNT])
        res[label] = (float(np.mean(aucs)), len(aucs), float(ov.mean()))
        print(f"  [{name:9s} {label:5s}] n={mask.sum():6d}  presence-AUC={res[label][0]:.4f} "
              f"({len(aucs)} cards)  top-H overlap={res[label][2]:.4f}", flush=True)
    return res


def main():
    torch.manual_seed(SEED)
    np.random.seed(SEED)
    z = np.load(DATA, allow_pickle=True)
    enc = Ragged(z, "enc")
    tgt = z["target"].astype(np.float32)
    meta = z["meta"]
    vocab = z["vocab"]
    print(f"{len(meta)} samples, vocab={len(vocab)}, align_rate={float(z['align_rate']):.4%}",
          flush=True)

    # ---- game-disjoint split ----
    games = np.unique(meta[:, M_GAME])
    rng = np.random.RandomState(SEED)
    rng.shuffle(games)
    n_held = max(1, len(games) // 10)
    held_games = set(games[:n_held].tolist())
    is_held = np.asarray([g in held_games for g in meta[:, M_GAME]])
    train = np.where(~is_held)[0]
    held = np.where(is_held)[0]
    print(f"split: {len(train)} train / {len(held)} held-out "
          f"({len(games) - n_held}/{n_held} games)", flush=True)

    # ---- archetype-average baseline from TRAIN split ----
    tb = np.minimum(meta[:, M_TURN], 12)
    n_arch = int(meta[:, M_ARCH].max()) + 1
    glob = tgt[train].mean(0)
    arch_mean = np.tile(glob, (n_arch, 1))
    at_mean = np.tile(glob, (n_arch, 13, 1))
    for a in range(n_arch):
        am = train[meta[train, M_ARCH] == a]
        if len(am):
            arch_mean[a] = tgt[am].mean(0)
        for t in range(13):
            m = am[tb[am] == t] if len(am) else am
            at_mean[a, t] = tgt[m].mean(0) if len(m) >= 30 else arch_mean[a]
    base_scores = at_mean[meta[held, M_ARCH], tb[held]]

    # ---- model ----
    dev = torch.device("mps" if torch.backends.mps.is_available() else "cpu")
    arch_json = json.load(open(os.path.join(ROOT, "model/az/grimm_imit_v11_arch.json")))
    base = NN.MyModel(*arch_json["model"], policy_tanh=arch_json.get("policy_tanh", False),
                      decoder_vocab=arch_json.get("decoder_vocab"))
    base.load_state_dict(torch.load(INIT, map_location="cpu"))
    model = BeliefNet(base, len(vocab)).to(dev)
    if FREEZE:
        for p in list(model.encoder_bag.parameters()) + list(model.encoder.parameters()):
            p.requires_grad_(False)
    groups = [{"params": model.head.parameters(), "lr": LR_HEAD}]
    if not FREEZE:
        groups.append({"params": list(model.encoder_bag.parameters())
                       + list(model.encoder.parameters()), "lr": LR_ENC})
    opt = torch.optim.AdamW(groups, weight_decay=1e-2)
    lossf = torch.nn.PoissonNLLLoss(log_input=True)
    print(f"device={dev} params={sum(p.numel() for p in model.parameters()):,} "
          f"encoder={'FROZEN' if FREEZE else f'fine-tuned lr={LR_ENC}'}", flush=True)

    def batch(ids):
        i, v, o = collate(enc, ids)
        return (torch.tensor(i, dtype=torch.int32, device=dev),
                torch.tensor(v, dtype=torch.float32, device=dev),
                torch.tensor(o, dtype=torch.int64, device=dev),
                torch.tensor(tgt[ids], device=dev))

    def held_loss():
        model.eval()
        tot = n = 0
        with torch.no_grad():
            for k in range(0, len(held), 2048):
                ii, vv, oo, yy = batch(held[k:k + 2048])
                tot += float(lossf(model(ii, vv, oo), yy)) * len(yy)
                n += len(yy)
        model.train()
        return tot / max(1, n)

    best = float("inf")
    for ep in range(EPOCHS):
        perm = train.copy()
        np.random.shuffle(perm)
        run = nb = 0
        for k in range(0, len(perm) - BS + 1, BS):
            ii, vv, oo, yy = batch(perm[k:k + BS])
            loss = lossf(model(ii, vv, oo), yy)
            opt.zero_grad()
            loss.backward()
            opt.step()
            run += float(loss.detach())
            nb += 1
            if nb % 50 == 0:
                print(f"  ep{ep} {nb}/{len(perm) // BS} train_nll={run / nb:.4f}", flush=True)
        hl = held_loss()
        print(f"epoch {ep}: train_nll={run / max(1, nb):.4f}  held_nll={hl:.4f}", flush=True)
        if hl < best:
            best = hl
            torch.save({"state_dict": model.state_dict(), "vocab": vocab.tolist(),
                        "arch": arch_json["model"], "init": os.path.basename(INIT),
                        "held_nll": hl}, OUT)
            print(f"  saved {OUT}", flush=True)

    # ---- final eval on held-out with the BEST checkpoint ----
    model.load_state_dict(torch.load(OUT, map_location=dev)["state_dict"])
    model.eval()
    preds = np.zeros((len(held), len(vocab)), dtype=np.float32)
    with torch.no_grad():
        for k in range(0, len(held), 2048):
            ii, vv, oo, _ = batch(held[k:k + 2048])
            preds[k:k + 2048] = torch.exp(model(ii, vv, oo)).cpu().numpy()
    print("\n==== held-out metrics (model vs archetype-average baseline) ====", flush=True)
    mres = report("belief_v0", preds, tgt[held].astype(np.int32), meta[held])
    bres = report("arch-base", base_scores, tgt[held].astype(np.int32), meta[held])
    print("\nheadline: model must beat baseline on both metrics")
    for ph in ("all", "T1-6", "T7+"):
        print(f"  {ph:5s}: AUC {mres[ph][0]:.4f} vs {bres[ph][0]:.4f} "
              f"({mres[ph][0] - bres[ph][0]:+.4f})   "
              f"overlap {mres[ph][2]:.4f} vs {bres[ph][2]:.4f} "
              f"({mres[ph][2] - bres[ph][2]:+.4f})")


if __name__ == "__main__":
    main()
