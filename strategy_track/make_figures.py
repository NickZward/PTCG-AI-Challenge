#!/usr/bin/env python3
"""Figures for the Kaggle Strategy Track writeup.

Every number here is a measured project result. Sources are noted per figure so the
values can be re-verified against SESSION_HANDOFF.md / driver.log / gate logs.
Edit DATA at the top; the plotting code below is intentionally boring.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- house style
INK      = "#1b1b1f"
MUTED    = "#8a8a94"
GRID     = "#e3e3e8"
WIN      = "#2f7d4f"   # beat / accepted
LOSS     = "#b4433a"   # lost the gate
NEUTRAL  = "#4a6fa5"
ACCENT   = "#c8892a"

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "savefig.bbox": "tight",
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.7,
    "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})

def title(ax, main, sub=None, pad=None):
    """Header with a point-based subtitle offset so it never collides on tall axes."""
    ax.set_title(main, loc="left", fontsize=11.5, fontweight="bold",
                 pad=(pad if pad is not None else (24 if sub else 8)))
    if sub:
        ax.annotate(sub, xy=(0, 1), xycoords="axes fraction",
                    textcoords="offset points", xytext=(0, 7),
                    fontsize=8.6, color=MUTED, va="bottom", ha="left")

def footer(fig, text):
    fig.text(0.008, -0.015, text, fontsize=7, color=MUTED, va="top")


# ============================================================ FIG 1
# Source: 4 rules-pilot builds, each gated vs grimm_v12_live on round_robin.
def fig1_complexity():
    decks = ["Teal Mask\nOgerpon ex", "Dudunsparce", "M-Lucario", "M-Kangaskhan"]
    subeng = [1, 3, 4, 5]
    wr     = [OGER_GATE, 38.9, 20.0, 11.1]
    n      = [90, 90, 90, 45]
    err    = [7 if k >= 90 else 10 for k in n]

    fig, ax = plt.subplots(figsize=(6.6, 4.1))
    ax.errorbar(subeng, wr, yerr=err, fmt="o", ms=9, color=NEUTRAL,
                ecolor=MUTED, elinewidth=1.2, capsize=4, zorder=3)
    z = np.polyfit(subeng, wr, 1)
    xs = np.linspace(0.6, 5.4, 50)
    ax.plot(xs, np.polyval(z, xs), "--", color=ACCENT, lw=1.4, zorder=2,
            label=f"least squares: {z[0]:.1f} pp per sub-engine")
    ax.axhline(50, color=LOSS, lw=1, ls=":", zorder=1)
    ax.text(5.35, 51, "parity with champion", ha="right", va="bottom",
            fontsize=7.6, color=LOSS)

    offs = [(0, -34), (18, 14), (16, 14), (0, 20)]
    for x, y, d, o in zip(subeng, wr, decks, offs):
        ax.annotate(d, (x, y), textcoords="offset points", xytext=o,
                    ha="center", fontsize=8.4, color=INK)
    ax.set_xlabel("Distinct sub-engines the deck must assemble to function")
    ax.set_ylabel("Rules-pilot win rate vs. frozen champion (%)")
    ax.set_xticks([1, 2, 3, 4, 5]); ax.set_xlim(0.6, 5.4); ax.set_ylim(0, 82)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    title(ax, "Fig 1 — Deck complexity caps the pilot",
          "Same author, same engine, same opponent. Each pilot refined until it stopped improving.")
    footer(fig, "Error bars: ±7pp at N=90, ±10pp at N=45 (measured tournament noise).")
    fig.savefig(OUT / "fig1_deck_complexity.png"); plt.close(fig)


# ============================================================ FIG 2
# Source: every gate this project ran vs the frozen champion grimm_v12_live.
def fig2_challengers():
    """Every gated challenger in chronological order, against the reigning champion of
    its era. Four became the new champion — all of them before v12. Nothing since."""
    ch = CHALLENGERS
    labels = [f"{c[0]}   (vs {c[1]})" for c in ch]
    vals   = [c[2] for c in ch]
    cols   = [WIN if c[3] else LOSS for c in ch]

    fig, ax = plt.subplots(figsize=(7.6, 8.0))
    y = np.arange(len(ch))[::-1]                 # chronological, top to bottom
    ax.barh(y, vals, color=cols, height=0.72, zorder=3)
    ax.axvline(50, color=INK, lw=1.4, zorder=4)
    ax.axvspan(43, 57, color=MUTED, alpha=0.13, zorder=1)

    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=8.0)
    ax.set_xlabel("Win rate vs. the reigning champion (%)")
    ax.set_xlim(0, 100)
    for yy, v in zip(y, vals):
        ax.text(v + 1.4, yy, f"{v:.1f}", va="center", fontsize=7.4, color=MUTED)

    # divider: the moment v12 was crowned and progress stopped
    split = len(ch) - CROWN_INDEX - 0.5
    ax.axhline(split, color=INK, lw=1.1, ls="--", zorder=5)
    ax.text(99, split + 0.42, "the champion was built here  ↑",
            fontsize=8.2, color=WIN, ha="right", va="bottom", fontweight="bold")
    ax.text(99, split - 0.42, "↓  nothing beat it after this",
            fontsize=8.2, color=LOSS, ha="right", va="top", fontweight="bold")
    ax.set_ylim(-1.6, len(ch) - 0.3)
    ax.text(50.9, -1.0, " parity", fontsize=8, color=INK, va="center")

    n_ok = sum(1 for c in ch if c[3])
    title(ax, f"Fig 2 — {len(ch)} gated challengers; {n_ok} became champion, none after v12",
          "Green replaced the champion. Red did not. Progress was real, then it stopped.")
    footer(fig, "Gates from strategy_track/evidence/*.log. Later gates re-run on a verified-idle machine (Finding 2).")
    fig.savefig(OUT / "fig2_challengers.png"); plt.close(fig)


# ============================================================ FIG 3
# Source: lab gate vs observed live-ladder field win rate, same agent.
def fig3_lab_vs_field():
    pts = LAB_VS_FIELD
    fig, ax = plt.subplots(figsize=(6.6, 5.2))
    LO, HI = 8, 78
    ax.set_xlim(LO, HI); ax.set_ylim(LO, 72)

    ax.plot([LO, 72], [LO, 72], "--", color=MUTED, lw=1.1, zorder=1)
    ax.text(66, 63, "if the lab agreed\nwith the field", fontsize=7.6, color=MUTED,
            rotation=41, rotation_mode="anchor", ha="center", va="center")

    # label placement tuned per point to avoid collisions
    lbl = {"M-Lucario": (12, 8), "Dudunsparce": (11, -20),
           "Grimmsnarl (champion)": (-11, 12), "Ogerpon": (12, -14)}
    for name, lab, field, note in pts:
        col = ACCENT if "Lucario" in name else NEUTRAL
        ax.scatter(lab, field, s=100, color=col, zorder=5, edgecolor="white", lw=1.4)
        ax.annotate(f"{name}\n{note}", (lab, field), textcoords="offset points",
                    xytext=lbl[name], fontsize=8, color=INK, va="center",
                    ha="left" if lbl[name][0] > 0 else "right")

    ml = [p for p in pts if "Lucario" in p[0]][0]
    mid = (ml[1] + ml[2]) / 2
    ax.annotate("", xy=(ml[1], ml[2] - 1.2), xytext=(ml[1], ml[1] + 1.0),
                arrowprops=dict(arrowstyle="->", color=ACCENT, lw=2.0), zorder=4)
    ax.text(ml[1] + 2.0, mid + 1.6, "+31.9 pp", ha="left",
            fontsize=9.5, color=ACCENT, va="center", fontweight="bold")
    ax.text(ml[1] + 2.0, mid - 2.6, "our veto was wrong", ha="left",
            fontsize=8, color=ACCENT, va="center")

    ax.set_xlabel("Lab: win rate vs. our frozen champion (%)")
    ax.set_ylabel("Field: win rate on the live ladder (%)")
    title(ax, "Fig 3 — The lab gate misranks agents",
          "We vetoed the M-Lucario agent on its lab score. It was submitted anyway.")
    footer(fig, "A gate measures an agent against ONE opponent — our champion — not against the field's composition.")
    fig.savefig(OUT / "fig3_lab_vs_field.png"); plt.close(fig)


# ============================================================ FIG 4
# Source: 2x2 ablation on 1% of the corpus, top-1 action agreement.
def fig4_imitation():
    bars = [
        ("Uniform random\nover legal actions", 24.8, MUTED, "baseline"),
        ("Original model\n(both bugs present)", 30.5, LOSS, "our v1"),
        ("Always pick first\nlegal index", 33.0, MUTED, "baseline"),
        ("Both bugs fixed", 60.4, WIN, "our v2"),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    x = np.arange(len(bars))
    ax.bar(x, [b[1] for b in bars], color=[b[2] for b in bars], width=0.62, zorder=3)
    for i, b in enumerate(bars):
        ax.text(i, b[1] + 1.1, f"{b[1]}%", ha="center", fontsize=9.5, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels([b[0] for b in bars], fontsize=8.3)
    ax.set_ylabel("Top-1 action agreement with the teacher (%)")
    ax.set_ylim(0, 70)

    ax.annotate("", xy=(1, 37.0), xytext=(2, 37.0),
                arrowprops=dict(arrowstyle="<->", color=LOSS, lw=1.4))
    ax.text(1.5, 38.6, "our model was WORSE\nthan a constant", ha="center",
            fontsize=8.2, color=LOSS, fontweight="bold", va="bottom")

    title(ax, "Fig 4 — Two bugs, not the architecture, caused our accuracy plateau",
          "Off-by-one action alignment in the replay parser + a degenerate regression loss.")
    footer(fig, "Always quote both baselines. Without them, 30.5% reads as progress.")
    fig.savefig(OUT / "fig4_imitation_ablation.png"); plt.close(fig)


# ============================================================ FIG 5
# Source: Dudunsparce build ladder, all gated vs the same champion.
def fig5_search():
    steps = [
        ("Imitation policy\nalone", 22.2, NEUTRAL),
        ("Hand-written\nrules pilot", 31.9, NEUTRAL),
        ("Imitation + self-play\nvalue + search", 37.8, WIN),
        ("Rules pilot\n+ tuned knobs", 38.9, NEUTRAL),
    ]
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    x = np.arange(len(steps))
    ax.bar(x, [s[1] for s in steps], color=[s[2] for s in steps], width=0.6, zorder=3)
    for i, s in enumerate(steps):
        ax.text(i, s[1] + 0.9, f"{s[1]}%", ha="center", fontsize=9.5, fontweight="bold")

    ax.plot([0, 0, 2, 2], [42.6, 44.2, 44.2, 42.6], color=ACCENT, lw=1.5, zorder=4)
    ax.text(1.0, 45.0, "+15.6 pp from search on a learned value",
            fontsize=8.8, color=ACCENT, fontweight="bold", ha="center", va="bottom")

    ax.set_xticks(x); ax.set_xticklabels([s[0] for s in steps], fontsize=8.3)
    ax.set_ylabel("Win rate vs. frozen champion (%)")
    ax.set_ylim(0, 50)
    title(ax, "Fig 5 — More imitation data bought nothing; search bought 15.6 points",
          "Same deck, same corpus. Doubling the corpus moved this agent 24.4% → 22.2% → 20.0%.")
    footer(fig, "Both branches asymptote near 39% — the hand-written pilot's ceiling for this deck.")
    fig.savefig(OUT / "fig5_value_search.png"); plt.close(fig)


# ============================================================ FIG 6
def fig6_targeted_cell():
    """Targeted self-play against a NAMED weak matchup: the cell moves, the mirror pays.
    Values verbatim from model/az/azloop/driver.log (iter 9 and iter 25 gate lines)."""
    labels = ["Champion\n(baseline)", "Self-play\niteration 9", "Self-play\niteration 25"]
    cell   = [37.8, 40.0, 57.8]      # vs the ogerpon_v1 sparring agent
    overall= [50.0, 51.1, 46.7]      # vs the frozen champion itself

    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    x = np.arange(len(labels)); w = 0.36
    b1 = ax.bar(x - w/2, cell, w, color=ACCENT, zorder=3,
                label="vs. Ogerpon — the targeted weak matchup")
    b2 = ax.bar(x + w/2, overall, w, color=NEUTRAL, zorder=3,
                label="vs. the frozen champion — overall strength")
    for bars, vals in ((b1, cell), (b2, overall)):
        for r, v in zip(bars, vals):
            ax.text(r.get_x() + r.get_width()/2, v + 0.9, f"{v}%", ha="center",
                    fontsize=8.8, fontweight="bold")

    ax.axhline(50, color=INK, lw=1, ls=":", zorder=2)
    # bracket over the two gold bars: the gain on the targeted matchup
    gx0, gx1 = -w/2, 2 - w/2
    ax.plot([gx0, gx0, gx1, gx1], [64.5, 66.5, 66.5, 64.5],
            color=ACCENT, lw=1.5, zorder=4)
    ax.text((gx0 + gx1) / 2, 67.4, "+20.0 pp on the targeted matchup",
            fontsize=8.8, color=ACCENT, fontweight="bold", ha="center", va="bottom")
    # the price, in clear space above the shorter blue bars
    ax.text(0.86, 57.4, "overall strength 50.0 → 46.7 (−3.3 pp) — so we did not ship it",
            fontsize=8, color=NEUTRAL, ha="center", va="center")

    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.6)
    ax.set_ylabel("Win rate (%)"); ax.set_ylim(0, 76)
    ax.legend(frameon=False, fontsize=8.2, ncol=2, loc="upper center",
              bbox_to_anchor=(0.5, -0.13), columnspacing=2.0, handlelength=1.4)
    title(ax, "Fig 6 — Targeted self-play moves a named weakness, and charges for it",
          "Broad self-play never beat the champion. Aiming it at one matchup did — the only method here that moved a named cell.")
    fig.savefig(OUT / "fig6_targeted_cell.png"); plt.close(fig)


# ============================================================ DATA
# >>> All values below are project measurements. Update here, not in the plots.
# ogerpon_v1 vs grimm_v12_live. Four N=90 runs: 71.1 / 65.6 / 65.6 / 64.4 (pooled 66.7%).
# We publish the CLEAN verified-idle run — the most defensible and the most conservative.
OGER_GATE = 64.4

# (challenger, opponent it was gated against, win%, did it become the new champion)
# Chronological. Sources: strategy_track/evidence/*.log and SESSION_HANDOFF.md.
CHALLENGERS = [
    ("imitation v2 + search",        "rules v17", 73.3, True),
    ("v4  representation v2",        "v2",        73.3, True),
    ("v5  feat-2 from scratch",      "v4",        26.7, False),
    ("v6  top-player fine-tune",     "v4",        71.1, True),
    ("v7  endgame blend",            "control",   51.1, False),
    ("v8  fresh-data fine-tune",     "v6",        53.3, False),
    ("v9  #1-player fine-tune",      "v6",        51.2, False),
    ("v10 opponent modelling",       "control",   42.2, False),
    ("v11 feature graft",            "v6",        51.1, False),
    ("v12 graft + deck + search fix","v11",       54.5, True),
    ("v14 early-tempo boost",        "v12",       52.3, False),
    ("v15 mirror-weighted",          "v12",       44.4, False),
    ("v16 behind-in-mirror",         "v12",       42.2, False),
    ("v17 scaled 34M model",         "v12",       46.7, False),
    ("v18 cross-deck transfer",      "v12",       24.4, False),
    ("v19 new-meta fine-tune",       "v12",       37.8, False),
    ("belief-informed search",       "v12",       44.4, False),
    ("2-ply deeper search",          "v12",       48.9, False),
    ("AZ self-play value, iter 1",   "v12",       48.9, False),
    ("AZ self-play value, iter 9",   "v12",       51.1, False),
    ("AZ self-play value, iter 25",  "v12",       46.7, False),
]
CROWN_INDEX = 9   # index of v12 — the last challenger that became champion

LAB_VS_FIELD = [
    # (agent, lab gate %, live ladder field %, note)
    ("M-Lucario",   20.0, 51.9, "n=27 ladder"),
    ("Dudunsparce", 38.9, 44.4, "n=36 ladder"),
    ("Grimmsnarl (champion)", 50.0, 55.4, "by definition = 50 in lab"),
    ("Ogerpon",     65.6, 57.6, "n=35 ladder"),
]

MATCHUP_DECKS = ["Grimmsnarl\n(champion)", "Ogerpon"]
MATCHUP_OPPS  = ["Grimmsnarl", "Ogerpon", "Dudunsparce", "M-Lucario", "Alakazam", "Dipplin"]
MATCHUP_GRID  = [
    [65.6, 37.8, 62.0, np.nan, 42.0, 52.0],   # champion
    [82.0, np.nan, np.nan, np.nan, np.nan, np.nan],  # ogerpon (thin ladder sample)
]

# ============================================================ FIG 7
# Source: my-agent/{ogerpon_v1,grimm_v12_live}/deck.csv resolved via EN_Card_Data.csv
DECK_ROLES = ["Pokémon", "Energy", "Search & recovery", "Supporters", "Stadium / tools"]
ROLE_COLS  = ["#2f7d4f", "#c8892a", "#4a6fa5", "#7a5ea8", "#8a8a94"]
DECK_COMP = {
    "Teal Mask Ogerpon ex\n1 sub-engine": [4, 20, 15, 15, 6],
    "Marnie's Grimmsnarl ex\n3 sub-engines": [18, 10, 15, 11, 6],
}
DECK_NOTE = {
    "Teal Mask Ogerpon ex\n1 sub-engine":
        "4 cards, ONE species. No evolution line, no tech attacker.\n"
        "20 Energy — a third of the deck — so a turn without an attack is near-impossible.",
    "Marnie's Grimmsnarl ex\n3 sub-engines":
        "18 Pokémon across 4 lines: Grimmsnarl (Stage 2, 320 HP), Froslass, Munkidori, Snorunt.\n"
        "Three engines must be online at once — which is exactly what makes it hard to pilot.",
}

def fig7_decks():
    fig, ax = plt.subplots(figsize=(8.0, 3.6))
    names = list(DECK_COMP)
    ypos = [1, 0]
    for name, y in zip(names, ypos):
        left = 0
        for role, col, n in zip(DECK_ROLES, ROLE_COLS, DECK_COMP[name]):
            ax.barh(y, n, left=left, color=col, height=0.42, zorder=3,
                    edgecolor="white", lw=1.2)
            if n >= 6:
                ax.text(left + n / 2, y, str(n), ha="center", va="center",
                        color="white", fontsize=9, fontweight="bold", zorder=4)
            else:
                # small segments (the 4-card Ogerpon line) get an outside callout —
                # this is the single most important count in the figure
                ax.text(left + n / 2, y + 0.25, str(n), ha="center", va="bottom",
                        color=col, fontsize=10, fontweight="bold", zorder=4)
            left += n
        ax.text(0, y - 0.32, DECK_NOTE[name], fontsize=7.9, color=MUTED,
                va="top", ha="left")

    ax.set_yticks(ypos); ax.set_yticklabels(names, fontsize=9.2)
    ax.set_xlim(0, 60); ax.set_ylim(-0.75, 1.55)
    ax.set_xlabel("Cards (deck is exactly 60)")
    ax.grid(axis="y", visible=False)
    handles = [matplotlib.patches.Patch(color=c, label=r)
               for c, r in zip(ROLE_COLS, DECK_ROLES)]
    ax.legend(handles=handles, frameon=False, fontsize=8, ncol=5,
              loc="upper left", bbox_to_anchor=(0, 1.13), columnspacing=1.1,
              handlelength=1.3)
    title(ax, "Fig 7 — The two submitted decks, by role",
          "Opposite ends of the complexity axis in Fig 1 — and opposite failure modes.",
          pad=44)
    footer(fig, "Counts resolved from each agent's deck.csv against the official EN card data.")
    fig.savefig(OUT / "fig7_decks.png"); plt.close(fig)


if __name__ == "__main__":
    fig1_complexity(); fig2_challengers(); fig3_lab_vs_field()
    fig4_imitation();  fig5_search();      fig6_targeted_cell()
    fig7_decks()
    print("wrote:")
    for p in sorted(OUT.glob("*.png")):
        print("  ", p.name, f"{p.stat().st_size//1024} KB")
