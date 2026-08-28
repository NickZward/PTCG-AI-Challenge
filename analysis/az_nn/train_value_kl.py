#!/usr/bin/env python3
"""KL-ANCHORED SELF-PLAY VALUE REFINEMENT — the value head is the measured bottleneck.

Trains on states OUR OWN agent reaches (gen_value_selfplay output, exact margins, T25 horizon),
with the policy held in place by a distillation anchor to the frozen reference net, so self-play
cannot drag the weights off the experts (the documented historical failure mode).

  loss = Huber(v, value_target) + KL_W * KL(ref_policy || new_policy)   over legal candidates
  value_target = (1-VLAM)*(+/-1 win) + VLAM*clip(2*margin)              (exact margins)

Held-out = the REAL-ladder corpus (our agents' actual field games, real outcomes) — the honest
distribution. Reported per epoch: value AUC by game phase on real states (the metric that must
move), plus policy top-1 agreement vs the reference (the anchor gauge; must stay ~>97%).

Usage: train_value_kl.py <selfplay1.npz,selfplay2.npz,...> <realladder.npz> --init=<ckpt.pth>
                         [--out=grimm_imit_v13] [--epochs=3] [--bs=128] [--lr=5e-5]
                         [--kl=1.0] [--vlam=0.4] [--model=128,8,512,4,4]
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
import nn_common as NN                                        # noqa: E402
from train_imit_v2 import Ragged, collate, load, M_TGT, M_NCAND, M_STYPE, M_TURN, M_WON, \
    M_WR, M_OPP, M_MARGIN, M_PID                              # noqa: E402


def auc(scores, labels):
    """Rank AUC (Mann-Whitney), ties averaged."""
    order = np.argsort(scores)
    ranks = np.empty(len(scores)); ranks[order] = np.arange(1, len(scores) + 1)
    # average ties
    s = np.asarray(scores)
    for v in np.unique(s):
        m = s == v
        if m.sum() > 1:
            ranks[m] = ranks[m].mean()
    pos = labels > 0.5
    n1, n0 = int(pos.sum()), int((~pos).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    return (ranks[pos].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    F = {a.split("=")[0].lstrip("-"): (a.split("=", 1)[1] if "=" in a else "1")
         for a in sys.argv[1:] if a.startswith("--")}
    train_paths = args[0].split(",")
    held_path = args[1]
    name = F.get("out", "grimm_imit_v13")
    epochs = int(F.get("epochs", 3)); bs = int(F.get("bs", 128))
    lr = float(F.get("lr", 5e-5)); KL_W = float(F.get("kl", 1.0))
    VLAM = float(F.get("vlam", 0.4))
    dims = [int(x) for x in F.get("model", "128,8,512,4,4").split(",")]

    enc, dec, meta, _ = load(train_paths)
    z0 = np.load(train_paths[0], allow_pickle=True)
    dvocab = int(z0["decoder_vocab"][0]); feat = int(z0["feat"][0])
    henc_z = np.load(held_path, allow_pickle=True)
    henc, hdec, hmeta = Ragged(henc_z, "enc"), Ragged(henc_z, "dec"), henc_z["meta"]
    print(f"train: {len(meta)} self-play states | held-out: {len(hmeta)} REAL ladder states | "
          f"feat={feat} vocab={dvocab}", flush=True)

    dev = torch.device(F.get("device", "mps" if torch.backends.mps.is_available() else "cpu"))
    model = NN.MyModel(*dims, policy_tanh=False, decoder_vocab=dvocab)
    model.load_state_dict(torch.load(F["init"], map_location="cpu"))
    model = model.to(dev)
    ref = NN.MyModel(*dims, policy_tanh=False, decoder_vocab=dvocab)
    ref.load_state_dict(torch.load(F["init"], map_location="cpu"))
    ref = ref.to(dev).eval()
    for p in ref.parameters():
        p.requires_grad_(False)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)

    def forward(m, E, D, ids):
        maxc = int(meta_of[ids, M_NCAND].max())
        ei, ev, eo = collate(E, ids)
        di, dv, do = collate(D, ids, pad_to=maxc)
        v, p = m(torch.as_tensor(ei, dtype=torch.int32, device=dev),
                 torch.as_tensor(ev, dtype=torch.float32, device=dev),
                 torch.as_tensor(eo, dtype=torch.int32, device=dev),
                 torch.as_tensor(di, dtype=torch.int32, device=dev),
                 torch.as_tensor(dv, dtype=torch.float32, device=dev),
                 torch.as_tensor(do, dtype=torch.int32, device=dev))
        return v, p, maxc

    @torch.inference_mode()
    def eval_real(m, chunk=256):
        """Value AUC by phase + policy agreement vs ref, on the REAL ladder held-out."""
        global meta_of
        meta_of = hmeta
        vals = np.zeros(len(hmeta)); agree = tot = 0
        for i in range(0, len(hmeta), chunk):
            ids = np.arange(i, min(i + chunk, len(hmeta)))
            ids = ids[np.argsort(hmeta[ids, M_NCAND])]
            v, p, maxc = forward(m, henc, hdec, ids)
            vr, pr, _ = forward(ref, henc, hdec, ids)
            nc = torch.as_tensor(hmeta[ids, M_NCAND], dtype=torch.long, device=dev)
            valid = torch.arange(maxc, device=dev)[None, :] < nc[:, None]
            pm = p.masked_fill(~valid, float("-inf")).argmax(1)
            prm = pr.masked_fill(~valid, float("-inf")).argmax(1)
            agree += int((pm == prm).sum()); tot += len(ids)
            vals[ids] = v.squeeze(1).float().cpu().numpy()
        out = {}
        won = hmeta[:, M_WON]
        turn = hmeta[:, M_TURN]
        out["auc_all"] = auc(vals, won)
        for lab, lo, hi in (("T1-6", 0, 6.5), ("T7-10", 6.5, 10.5), ("T11+", 10.5, 99)):
            m_ = (turn > lo) & (turn <= hi)
            out[f"auc_{lab}"] = auc(vals[m_], won[m_]) if m_.sum() > 100 else float("nan")
        out["agree_ref"] = agree / max(1, tot)
        return out

    global meta_of
    meta_of = hmeta
    base = eval_real(model)
    print("BASELINE (v11 head on real ladder states): " +
          "  ".join(f"{k}={v:.3f}" for k, v in base.items()), flush=True)

    ids_all = np.arange(len(meta))
    _mt = float(F.get("min-turn", 0))
    if _mt > 0:
        ids_all = ids_all[meta[:, M_TURN] >= _mt]
        print(f"--min-turn={_mt:g}: training on {len(ids_all)}/{len(meta)} states", flush=True)
    rng = np.random.default_rng(0)
    outdir = os.path.join(ROOT, "model/az")
    best = base["auc_all"]
    for ep in range(epochs):
        t0 = time.time(); model.train()
        rng.shuffle(ids_all)
        tot = totv = totk = 0.0; nb = len(ids_all) // bs
        meta_of = meta
        for i in range(nb):
            b = ids_all[i * bs:(i + 1) * bs]
            b = b[np.argsort(meta[b, M_NCAND])]
            opt.zero_grad(set_to_none=True)
            v, p, maxc = forward(model, enc, dec, b)
            with torch.inference_mode():
                _, pref, _ = forward(ref, enc, dec, b)
            pref = pref.clone()
            nc = torch.as_tensor(meta[b, M_NCAND], dtype=torch.long, device=dev)
            valid = torch.arange(maxc, device=dev)[None, :] < nc[:, None]
            win = np.where(meta[b, M_WON] > 0.5, 1.0, -1.0)
            marg = np.clip(meta[b, M_MARGIN] * 2.0, -1.0, 1.0)
            vt = torch.as_tensor((1 - VLAM) * win + VLAM * marg,
                                 dtype=torch.float32, device=dev)[:, None]
            lv = torch.nn.functional.huber_loss(v, vt, delta=0.5)
            logp_new = torch.log_softmax(p.masked_fill(~valid, float("-inf")), 1)
            logp_ref = torch.log_softmax(pref.masked_fill(~valid, float("-inf")), 1)
            pr = logp_ref.exp()
            kl = (pr * (logp_ref - logp_new)).masked_fill(~valid, 0.0).sum(1).mean()
            loss = lv + KL_W * kl
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            tot += float(loss.detach()); totv += float(lv.detach()); totk += float(kl.detach())
        model.eval()
        ev = eval_real(model)
        print(f"epoch {ep}: loss {tot/nb:.4f} (val {totv/nb:.4f} kl {totk/nb:.4f})  REAL: " +
              "  ".join(f"{k}={v:.3f}" for k, v in ev.items()) + f"  {time.time()-t0:.0f}s",
              flush=True)
        if ev["auc_all"] > best and ev["agree_ref"] >= float(F.get("agree-floor", 0.97)):
            best = ev["auc_all"]
            torch.save(model.state_dict(), os.path.join(outdir, f"{name}_best.pth"))
            json.dump({"model": dims, "policy_tanh": False, "feat": feat,
                       "decoder_vocab": dvocab},
                      open(os.path.join(outdir, f"{name}_arch.json"), "w"))
            print(f"  -> saved (auc {best:.3f})", flush=True)
    print(f"BEST real-ladder value AUC: {best:.3f} (baseline {base['auc_all']:.3f})")


if __name__ == "__main__":
    main()
