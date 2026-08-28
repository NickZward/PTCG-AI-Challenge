#!/usr/bin/env python3
"""STEP 3 core: self-play training for a Transformer+MCTS agent, with a CURRICULUM stable.

Design (deliberate, vs the pure-mirror reference):
  - CORE signal = mirror self-play (both sides = the improving MCTS agent) -> strong policy that
    generalizes via the value net. This is the reference's proven climber.
  - CURRICULUM = a configurable fraction of games are played vs real rule opponents (Crustle,
    M-Lucario first — the decks that gate the low climb per the leaderboard-by-band meta). Only OUR
    side records samples there, so weak opponents give matchup COVERAGE without dominating the policy
    target (avoids the "weak clones distort the value signal" failure the project hit before).
  - T14 LADDER ADJUDICATION for value labels (project law: ladder stops ~T14, prize leader wins,
    deckout=loss) so the value target matches how the real ladder scores.
  - Value/policy targets follow the reference: backward TD(lambda) value blend + per-child MCTS
    advantage policy, combined masked Huber loss, AdamW.

run_training(config) returns the path to the best model. Same code runs locally (CPU smoke) and on
Kaggle (GPU scale) — only the config changes.
"""
import importlib.util
import os
import random
import sys
import time

import torch

import nn_common as NN
from mcts_agent import mcts_agent

from cg.game import battle_start, battle_finish, battle_select
from cg.api import to_observation_class

STOP_DEFAULT = 14


def _read_deck(path):
    return [int(x) for x in open(path).read().split()]


def _load_rule_agent(agent_dir):
    """Load a rule opponent's `agent(obs_dict)->list[int]` + its deck."""
    spec = importlib.util.spec_from_file_location("rule_" + os.path.basename(agent_dir),
                                                  os.path.join(agent_dir, "main.py"))
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    if agent_dir not in sys.path:
        sys.path.insert(0, agent_dir)
    spec.loader.exec_module(m)
    return m.agent, _read_deck(os.path.join(agent_dir, "deck.csv"))


def _adjudicate(cur):
    """T14 buzzer adjudication: prize leader (us=0) wins; deck breaks ties; -4 = exact tie."""
    P = cur.players
    p0, p1 = 6 - len(P[0].prize or []), 6 - len(P[1].prize or [])
    if p0 != p1:
        return 0 if p0 > p1 else 1
    d0, d1 = P[0].deckCount or 0, P[1].deckCount or 0
    if d0 != d1:
        return 0 if d0 > d1 else 1
    return -4


def _wrap(obs):
    """Build the observation dict our agents expect (mirror gen_policy_iter's `w`)."""
    return {"current": obs.get("current"), "select": obs.get("select"),
            "logs": obs.get("logs", []), "step": obs.get("step", 0),
            "remainingOverageTime": 600,
            "search_begin_input": obs.get("search_begin_input")}


def play_training_game(our_deck, model, opponent, cfg):
    """Play one game; record LearnSamples for MCTS-controlled side(s).

    opponent: None -> MIRROR (MCTS agent both sides, record both perspectives)
              (agent_fn, opp_deck) -> our MCTS agent vs a rule agent (record our side only)
    Returns (samples_by_side: [list,list], result_winner_index: int) or (None, None) if void.
    """
    stop = cfg["stop_turn"]
    search_count = cfg["search_count"]
    mirror = opponent is None
    if mirror:
        opp_deck_for_search = our_deck
        our_side = 0
    else:
        opp_agent, opp_full_deck = opponent
        opp_deck_for_search = opp_full_deck
        our_side = random.randint(0, 1)

    left_deck = list(our_deck) if our_side == 0 else (list(our_deck) if mirror else list(opp_full_deck))
    right_deck = list(our_deck) if mirror else (list(opp_full_deck) if our_side == 0 else list(our_deck))
    obs, _ = battle_start(left_deck, right_deck)
    if obs is None:
        return None, None

    samples = [[], []]
    result = None
    ended_natural = False
    final_cur = None
    steps = 0
    try:
        while steps < 4000:
            cur = obs.get("current") or {}
            final_cur = cur
            r = cur.get("result", -1)
            if r not in (None, -1):
                result = r
                ended_natural = True
                break
            if obs.get("select") is None:
                break
            turn = cur.get("turn", 0) or 0
            if cfg["t14_adjudicate"] and turn > stop:
                result = _adjudicate(to_observation_class(_wrap(obs)).current)
                break
            you = cur.get("yourIndex", 0)
            controls_mcts = mirror or (you == our_side)
            if controls_mcts:
                # opponent-aware determinization: model the REAL opponent deck in the search
                # (mirror -> our_deck; curriculum -> the opponent's deck) instead of neutral fill.
                sel, sample = mcts_agent(obs, our_deck, model,
                                         opp_deck=opp_deck_for_search,
                                         search_count=search_count)
                if sample is not None:
                    samples[you].append(sample)
                obs = battle_select([int(x) for x in sel])
            else:
                w = _wrap(obs)
                act = opp_agent(w)
                obs = battle_select([int(x) for x in act])
            steps += 1
    finally:
        battle_finish()

    if result is None or result == -4:
        return None, None
    # SHAPED terminal value per side (fixes passivity): a NATURAL win (took all prizes / opp decked)
    # is fully decisive (+/-1); a T14-buzzer result is scored by PRIZE MARGIN/6 so a bare 1-prize lead
    # (0.17) is worth far less than a decisive win -> pushes the agent to CLOSE games, not durdle.
    if ended_natural:
        term = {result: 1.0, 1 - result: -1.0}
    else:
        P = (final_cur or {}).get("players") or [{}, {}]
        p0 = 6 - len(P[0].get("prize") or [])
        p1 = 6 - len(P[1].get("prize") or [])
        m0 = max(-1.0, min(1.0, (p0 - p1) / 6.0))
        term = {0: m0, 1: -m0}
    return samples, term


def evaluate_fixed(our_deck, model, opponents, cfg):
    """Balanced eval: play each opponent eval_games times, alternating which side we take."""
    res = {}
    for name, (agent_fn, opp_deck) in opponents.items():
        wins = losses = voids = 0
        for g in range(cfg["eval_games"]):
            our_side = g % 2
            obs, _ = battle_start(list(our_deck) if our_side == 0 else list(opp_deck),
                                  list(opp_deck) if our_side == 0 else list(our_deck))
            if obs is None:
                voids += 1
                continue
            result = None
            steps = 0
            try:
                while steps < 4000:
                    cur = obs.get("current") or {}
                    r = cur.get("result", -1)
                    if r not in (None, -1):
                        result = r
                        break
                    if obs.get("select") is None:
                        break
                    turn = cur.get("turn", 0) or 0
                    if cfg["t14_adjudicate"] and turn > cfg["stop_turn"]:
                        result = _adjudicate(to_observation_class(_wrap(obs)).current)
                        break
                    you = cur.get("yourIndex", 0)
                    if you == our_side:
                        with torch.inference_mode():
                            sel, _ = mcts_agent(obs, our_deck, model, opp_deck=opp_deck,
                                                search_count=cfg["search_count"])
                        obs = battle_select([int(x) for x in sel])
                    else:
                        obs = battle_select([int(x) for x in agent_fn(_wrap(obs))])
                    steps += 1
            finally:
                battle_finish()
            if result is None or result == -4:
                voids += 1
            elif result == our_side:
                wins += 1
            else:
                losses += 1
        tot = wins + losses
        res[name] = (wins / tot if tot else float("nan"), wins, losses, voids)
    return res


def _label_and_collect(samples_by_side, term, sample_list, lam):
    """Backward TD(lambda) value labeling per MCTS-controlled side, from the SHAPED terminal value."""
    for side in range(2):
        seq = samples_by_side[side]
        if not seq:
            continue
        value = term[side]  # shaped terminal value in [-1,1] (decisive win=+1, bare T14 lead~+0.17)
        for sample in reversed(seq):
            label = (value + sample.value) * 0.5
            value = value * lam + sample.value * (1.0 - lam)
            sample.value = label
            sample_list.append(sample)


def _train_epoch(model, optimizer, sample_list, cfg, device):
    loss_fn_enc = torch.nn.HuberLoss(delta=0.2)
    loss_fn_dec = torch.nn.HuberLoss(reduction="none", delta=0.1)
    random.shuffle(sample_list)
    bs = cfg["batch_size"]
    nb = len(sample_list) // bs
    total = 0.0
    for i in range(nb):
        ie = _LI(); idd = _LI()
        mask = []
        label_enc = []
        label_dec = []
        for j in range(bs * i, bs * i + bs):
            s = sample_list[j]
            ie.add(s.sv_enc)
            idd.add(s.sv_dec)
            label_enc.append(s.value)
            label_dec.extend(s.policy)
            for _ in range(len(s.policy)):
                mask.append(1.0)
            for _ in range(64 - len(s.policy)):
                mask.append(0.0)
                label_dec.append(0.0)
                idd.offset.append(len(idd.index))
        mask_t = torch.tensor(mask, dtype=torch.float32, device=device).view(bs, -1)
        le = torch.tensor(label_enc, dtype=torch.float32, device=device).view(bs, -1)
        ld = torch.tensor(label_dec, dtype=torch.float32, device=device).view(bs, -1)
        optimizer.zero_grad()
        oe, od = model(
            torch.tensor(ie.index, dtype=torch.int32, device=device),
            torch.tensor(ie.value, dtype=torch.float32, device=device),
            torch.tensor(ie.offset, dtype=torch.int32, device=device),
            torch.tensor(idd.index, dtype=torch.int32, device=device),
            torch.tensor(idd.value, dtype=torch.float32, device=device),
            torch.tensor(idd.offset, dtype=torch.int32, device=device))
        loss_enc = loss_fn_enc(oe, le)
        loss_dec = loss_fn_dec(od, ld) * mask_t
        loss_dec = loss_dec.sum() / float(bs)
        loss = loss_enc + loss_dec
        loss.backward()
        optimizer.step()
        total += float(loss.detach())
    return total / max(1, nb)


class _LI:
    """Batch input builder (reference LearnInput)."""
    def __init__(self):
        self.index = []
        self.value = []
        self.offset = []

    def add(self, sv):
        count = len(self.index)
        self.index.extend(sv.index)
        self.value.extend(sv.value)
        for o in sv.offset:
            self.offset.append(o + count)


def _build_opponent_pool(cfg):
    """Weighted list of ('mirror' | (agent_fn, deck)) for training-game opponent sampling."""
    pool = []
    pool += ["mirror"] * cfg["mirror_weight"]
    loaded = {}
    for c in cfg["curriculum"]:
        agent_fn, deck = _load_rule_agent(c["dir"])
        loaded[os.path.basename(c["dir"])] = (agent_fn, deck)
        pool += [(agent_fn, deck)] * c["weight"]
    return pool, loaded


class _SV:
    """Minimal SparseVector for reconstructed warm-start samples (has .index/.value/.offset)."""
    __slots__ = ("index", "value", "offset")

    def __init__(self, index, value, offset):
        self.index, self.value, self.offset = index, value, offset


class _WS:
    """LearnSample-compatible wrapper for a warm-start expert decision."""
    __slots__ = ("sv_enc", "sv_dec", "value", "policy")

    def __init__(self, d):
        self.sv_enc = _SV(d["ei"], d["ev"], d["eo"])
        self.sv_dec = _SV(d["di"], d["dv"], d["do"])
        self.value = d["val"]
        self.policy = d["pol"]


def pretrain(model, optimizer, cfg, device):
    """#1 WARM-START: BC-imitate expert moves + ground the value net on expert outcomes BEFORE
    self-play, so self-play improves from expert-level play instead of random. Uses the SAME
    _train_epoch as self-play (warm-start samples are LearnSample-compatible)."""
    import pickle
    path = cfg.get("warmstart")
    if not path or not os.path.exists(path):
        print("no warm-start data -> self-play from scratch (weak).", flush=True)
        return
    samples = [_WS(d) for d in pickle.load(open(path, "rb"))]
    epochs = cfg.get("pretrain_epochs", 4)
    print(f"WARM-START: {len(samples)} expert decisions x {epochs} epochs", flush=True)
    model.train()
    for ep in range(epochs):
        loss = _train_epoch(model, optimizer, samples, cfg, device)
        print(f"  pretrain epoch {ep}: loss {loss:.4f}", flush=True)


def run_training(cfg):
    device = torch.device(cfg.get("device") or ("cuda" if torch.cuda.is_available() else "cpu"))
    if device.type == "cuda":
        cap = torch.cuda.get_device_capability()
        if cap[0] < 7:  # P100 (sm_60) is unsupported by Kaggle's current PyTorch -> forward passes
            print(f"WARNING: GPU capability {cap} < 7.0 (e.g. P100) unsupported by this PyTorch; "
                  f"falling back to CPU to avoid the silent 0-samples failure.", flush=True)
            device = torch.device("cpu")
    os.makedirs(cfg["out_dir"], exist_ok=True)
    # persist the model architecture so the deployed agent loads matching dims (no shape mismatch)
    import json as _json
    _json.dump({"model": list(cfg["model"])}, open(os.path.join(cfg["out_dir"], "model_arch.json"), "w"))
    our_deck = _read_deck(os.path.join(cfg["deck_dir"], "deck.csv"))
    pool, eval_opps = _build_opponent_pool(cfg)
    print(f"device={device}  deck={cfg['deck_dir']}  curriculum={list(eval_opps)}  "
          f"mirror_w={cfg['mirror_weight']}  search={cfg['search_count']}", flush=True)

    model = NN.MyModel(*cfg["model"]).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["lr"])

    pretrain(model, optimizer, cfg, device)   # #1 warm-start from expert replays (if provided)

    best_path = None
    for it in range(cfg["iterations"]):
        t0 = time.time()
        ckpt = os.path.join(cfg["out_dir"], f"model{it}.pth")
        torch.save(model.state_dict(), ckpt)

        # ---- eval (curriculum win-rate) ----
        model.eval()
        with torch.inference_mode():
            ev = evaluate_fixed(our_deck, model, eval_opps, cfg)
        ev_str = "  ".join(f"{k}={v[0]*100:.0f}%({v[1]}-{v[2]})" for k, v in ev.items())
        print(f"[iter {it}] EVAL  {ev_str}", flush=True)

        # ---- self-play data collection ----
        sample_list = []
        gi = 0
        with torch.inference_mode():
            for g in range(cfg["games_per_iter"]):
                opp = random.choice(pool)
                opponent = None if opp == "mirror" else opp
                samples, term = play_training_game(our_deck, model, opponent, cfg)
                if samples is None:
                    continue
                _label_and_collect(samples, term, sample_list, cfg["lambda_td"])
                gi += 1
        # ---- train ----
        model.train()
        avg_loss = _train_epoch(model, optimizer, sample_list, cfg, device)
        print(f"[iter {it}] collected {len(sample_list)} samples from {gi} games; "
              f"train loss {avg_loss:.4f}; {time.time()-t0:.0f}s", flush=True)
        best_path = ckpt

    final = os.path.join(cfg["out_dir"], "model_final.pth")
    torch.save(model.state_dict(), final)
    print(f"saved final -> {final}")
    return final
