#!/usr/bin/env python3
"""Figure set v2 for the rebuilt Strategy Track writeup ("Fix the Instruments First").
Every number is a measured project result; sources in strategy_track/evidence/ and the
REFRESH/JUDGE/V41/TOP logs. Fig 8's final points update after the last ladder scrape.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

OUT = Path(__file__).parent / "figures_v2"
OUT.mkdir(exist_ok=True)

INK, MUTED, GRID = "#1b1b1f", "#8a8a94", "#e3e3e8"
WIN, LOSS, NEUTRAL, ACCENT = "#2f7d4f", "#b4433a", "#4a6fa5", "#c8892a"
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
    ax.set_title(main, loc="left", fontsize=11.5, fontweight="bold",
                 pad=(pad if pad is not None else (24 if sub else 8)))
    if sub:
        ax.annotate(sub, xy=(0, 1), xycoords="axes fraction", textcoords="offset points",
                    xytext=(0, 7), fontsize=8.6, color=MUTED, va="bottom", ha="left")

def footer(fig, text):
    fig.text(0.008, -0.015, text, fontsize=7, color=MUTED, va="top")


# ---- FIG 1: rules-pilot ceiling vs sub-engines (retained; the law imitation later dissolves)
def fig1():
    subeng, wr = [1, 3, 4, 5], [64.4, 38.9, 20.0, 11.1]
    names = ["Ogerpon\n(1 species)", "Dudunsparce", "M-Lucario", "M-Kangaskhan"]
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    ax.errorbar(subeng, wr, yerr=[7, 7, 7, 10], fmt="o", ms=9, color=NEUTRAL,
                ecolor=MUTED, capsize=4, zorder=3)
    z = np.polyfit(subeng, wr, 1); xs = np.linspace(0.6, 5.4, 40)
    ax.plot(xs, np.polyval(z, xs), "--", color=ACCENT, lw=1.4,
            label=f"{z[0]:.1f} pp per sub-engine")
    offs = [(0, -34), (18, 14), (16, 14), (0, 20)]
    for x, y, d, o in zip(subeng, wr, names, offs):
        ax.annotate(d, (x, y), textcoords="offset points", xytext=o, ha="center", fontsize=8.2)
    ax.axhline(50, color=LOSS, lw=1, ls=":")
    ax.set_xlabel("Distinct sub-engines the deck must assemble")
    ax.set_ylabel("Hand-written pilot win rate vs champion (%)")
    ax.set_xticks([1, 2, 3, 4, 5]); ax.set_ylim(0, 80); ax.legend(frameon=False, fontsize=8)
    title(ax, "Fig 1 — A scripted pilot's ceiling falls with deck complexity",
          "Four pilots, same author and harness. Imitation later dissolved this law: neural agents pilot multi-line decks.")
    footer(fig, "N=90 gates (N=45 for M-Kangaskhan), verified-idle machine.")
    fig.savefig(OUT / "fig1_complexity.png"); plt.close(fig)


# ---- FIG 2: the gated-challenger record, both arcs
def fig2():
    rows = [  # (label, %, champion_at_time, arc2, became_best)
        ("imitation v2 + search", 73.3, 1), ("v4 representation v2", 73.3, 1),
        ("v5 from scratch", 26.7, 0), ("v6 #1-player fine-tune", 71.1, 1),
        ("v7 endgame blend", 51.1, 0), ("v8 fresh data", 53.3, 0),
        ("v9 second #1 corpus", 51.2, 0), ("v10 opponent model", 42.2, 0),
        ("v11 feature graft", 51.1, 0), ("v12 graft+deck", 54.5, 1),
        ("v14 tempo boost", 52.3, 0), ("v15 mirror weight", 44.4, 0),
        ("v16 comeback weight", 42.2, 0), ("v17 scaled 34M", 46.7, 0),
        ("v18 cross-deck", 24.4, 0), ("v19 new-meta tune", 37.8, 0),
        ("belief search", 44.4, 0), ("2-ply search", 48.9, 0),
        ("AZ value iter1/9/25", 51.1, 0), ("kd fine-tune line", 51.5, 0),
        ("value-head refresh", 0, -1),  # AUC-rejected pre-gate
        ("— instrument audit: 5 bugs fixed —", -1, -2),
        ("oger palsystem imit", 59.7, 2), ("drag Dipam imit", 60.0, 2),
        ("oger Dipam v4i", 53.8, 2), ("DRAG v4 (#1 corpus)", 60.0, 3),
        ("drag veto layer", 46.7, 0), ("oger Ala-boost v5", 36.2, 0),
        ("drag_v5 fresh refresh", 54.6, 2), ("oger_v5b fresh refresh", 50.4, 0),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 8.6))
    y = np.arange(len(rows))[::-1]
    for yy, (lab, v, k) in zip(y, rows):
        if k == -2:
            ax.axhline(yy, color=INK, lw=1.1, ls="--")
            ax.text(97, yy + 0.35, "adversarial audit: five instrument bugs found & fixed",
                    fontsize=8, color=ACCENT, ha="right", fontweight="bold")
            continue
        col = WIN if k in (1, 3) else (ACCENT if k == 2 else LOSS)
        ax.barh(yy, max(v, 0), color=col, height=0.7, zorder=3)
        ax.text(max(v, 0) + 1.2, yy, f"{v:.1f}" if v >= 0 else "AUC-rejected",
                va="center", fontsize=7.2, color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([r[0] for r in rows], fontsize=7.8)
    ax.axvline(50, color=INK, lw=1.3)
    ax.set_xlim(0, 100); ax.set_xlabel("Win rate vs. the reigning best (%)")
    title(ax, "Fig 2 — 30+ gated challengers across two arcs",
          "Green replaced the best. Amber beat its own line post-audit. Red closed a lever with a number.")
    footer(fig, "All post-audit gates: N>=120 with independent replication; pooled values shown.")
    fig.savefig(OUT / "fig2_challengers.png"); plt.close(fig)


# ---- FIG 3: field composition by band
def fig3():
    archs = ["Grimmsnarl", "Alakazam", "Dragapult", "M-Lopunny", "Ogerpon",
             "M-Lucario", "M-Kang", "Crustle", "M-Starmie"]
    low = [16, 20, 8, 4, 8, 24, 8, 13, 3]      # our slots' observed low-band field (~500-700)
    top = [21.9, 16.3, 14.1, 13.1, 9.5, 7.5, 5.8, 1.2, 0.4]  # fresh 4,870-game top sample
    x = np.arange(len(archs)); w = 0.38
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    ax.bar(x - w/2, low, w, color=ACCENT, label="low band (~500-700): what a fresh submission meets")
    ax.bar(x + w/2, top, w, color=NEUTRAL, label="top band: what its teachers played against")
    ax.set_xticks(x); ax.set_xticklabels(archs, fontsize=7.8)
    ax.set_ylabel("share of field (%)"); ax.legend(frameon=False, fontsize=8)
    for xi, (l, t) in enumerate(zip(low, top)):
        if abs(l - t) >= 8:
            ax.annotate("", xy=(xi + w/2, t), xytext=(xi - w/2, l),
                        arrowprops=dict(arrowstyle="->", color=LOSS, lw=1.2))
    title(ax, "Fig 3 — The band-mismatch trap",
          "Imitations of top players are optimised for the top field, then dropped into a low band with different predators "
          "(Crustle stall: 13% low vs 1% top — and 12 counter-demonstrations exist in 14,245 games).")
    footer(fig, "Low band measured from our slots' replay drops; top band from the 4,870-game fresh dump.")
    fig.savefig(OUT / "fig3_bands.png"); plt.close(fig)


# ---- FIG 4: same recipe, bugged vs clean pipeline
def fig4():
    fig, ax = plt.subplots(figsize=(7.6, 4.3))
    pre = [("M-Lucario\n(v18)", 24.4), ("Dudunsparce\n(516 sides)", 22.2),
           ("Dudunsparce\n(1,549 sides)", 20.0), ("M-Lucario\npure-elite", 6.7)]
    post = [("Ogerpon\npalsystem", 59.7), ("Dragapult\nDipam", 60.0),
            ("Ogerpon\nDipam v4i", 53.8), ("Dragapult\n#1 corpus", 60.0)]
    xs1 = np.arange(len(pre)); xs2 = np.arange(len(post)) + len(pre) + 0.8
    ax.bar(xs1, [p[1] for p in pre], color=LOSS, width=0.62)
    ax.bar(xs2, [p[1] for p in post], color=WIN, width=0.62)
    for x, (l, v) in zip(xs1, pre): ax.text(x, v + 1, f"{v}", ha="center", fontsize=8.6, fontweight="bold")
    for x, (l, v) in zip(xs2, post): ax.text(x, v + 1, f"{v}", ha="center", fontsize=8.6, fontweight="bold")
    ax.set_xticks(list(xs1) + list(xs2))
    ax.set_xticklabels([p[0] for p in pre] + [p[0] for p in post], fontsize=7.4, rotation=12)
    ax.axvline(len(pre) - 0.1, color=INK, lw=1.1, ls="--")
    ax.text(len(pre) - 0.35, 64, "five bugs fixed →", fontsize=8.6, color=ACCENT,
            ha="right", fontweight="bold")
    ax.axhline(50, color=INK, lw=1, ls=":")
    ax.set_ylabel("win rate vs own-line best (%)"); ax.set_ylim(0, 70)
    title(ax, "Fig 4 — The same recipe, before and after the instrument audit",
          "Cross-deck imitation 'failed at every scale' — until the pipeline stopped lying. Right-side gates: N>=160 pooled, replicated.")
    footer(fig, "'Failure was the diagnosis of the tools, not the method.'")
    fig.savefig(OUT / "fig4_recipe_ab.png"); plt.close(fig)


# ---- FIG 5: the five bugs, measured costs
def fig5():
    bugs = [
        ("wins-only value collapse", "value head flat at +0.97 — asserts 'winning' 5 prizes down", 5),
        ("module-name collision", "same cell reads 78% / 34% / 0% by load order", 4),
        ("missing BLAS thread cap", "56x slower forwards; 94% of decisions with search silently off", 3),
        ("feature-version global", "opponent crashed to pick-first: a plausible 2.5% cell", 2),
        ("hard-coded encoder deck", "every 2nd-deck agent trained holding the wrong 60 (~24% flips)", 1),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.4))
    y = np.arange(len(bugs)) * 1.15
    ax.barh(y, [70, 60, 72, 74, 40], color=LOSS, height=0.5, zorder=3)
    for yy, (name, cost, _) in zip(y, bugs):
        ax.text(1.5, yy, name, va="center", fontsize=8.6, color="white", fontweight="bold", zorder=4)
        ax.text(1.5, yy - 0.42, cost, va="center", fontsize=7.4, color=INK, zorder=4)
    ax.set_yticks([]); ax.set_xlim(0, 100); ax.set_xticks([])
    for s in ("left", "bottom"): ax.spines[s].set_visible(False)
    ax.grid(False)
    title(ax, "Fig 5 — Five silent bugs, none visible in any training metric",
          "Found by adversarial audit with positive controls: instrument the OPPONENT as rigorously as the candidate.")
    footer(fig, "Bar length is illustrative severity; the annotation is the measured effect.")
    fig.savefig(OUT / "fig5_bugs.png"); plt.close(fig)


# ---- FIG 6: the veto A/B — transplant law
def fig6():
    fig, ax = plt.subplots(figsize=(6.6, 3.9))
    labels = ["baseline\n(no vetoes)", "veto A only\n(retreat fix)", "vetoes A+B\n(+ counter re-aim)"]
    vals = [50.0, 50.0, 46.7]
    fires = ["", "A fired 19x/120g", "A 35x + B 230x /120g"]
    cols = [NEUTRAL, ACCENT, LOSS]
    x = np.arange(3)
    ax.bar(x, vals, color=cols, width=0.56)
    for xi, (v, f) in enumerate(zip(vals, fires)):
        ax.text(xi, v + 0.7, f"{v}%", ha="center", fontsize=9.5, fontweight="bold")
        if f: ax.text(xi, 5, f, ha="center", fontsize=7.6, color="white", fontweight="bold")
    ax.axhline(50, color=INK, lw=1, ls=":")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8.4)
    ax.set_ylabel("head-to-head vs unmodified agent (%)"); ax.set_ylim(0, 60)
    title(ax, "Fig 6 — Expert patterns transplant their cost, not their skill",
          "Both vetoes copied measured #1-player behaviours; both preconditions objective; fire-verified — and the agent got worse.")
    footer(fig, "Mechanism: counters place one at a time; re-aiming mid-sequence splits placements the expert concentrates (his 'waste' is overkill that guarantees kills).")
    fig.savefig(OUT / "fig6_veto.png"); plt.close(fig)


# ---- FIG 7: final deck, annotated
def fig7():
    rows = [
        ("Dreepy / Drakloak / Dragapult ex  (4-4-3)", 11, WIN, "the engine: Phantom Dive, 200 + 6 bench counters"),
        ("Munkidori (1) + Budew (2)", 3, WIN, "counter movement + item-lock tempo"),
        ("Fezandipiti ex, Latias ex, Meowth ex", 3, WIN, "ability bodies: draw, free retreat, supporter fetch"),
        ("Energy (R4 P4 D2)", 10, ACCENT, "three-colour base"),
        ("Draw / search (Poffin, Ultra Ball, Poke Pad, Lillie x4...)", 19, NEUTRAL, "consistency engine"),
        ("Disruption (Crispin, Hammer, Jamming Tower x2, Unfair Stamp...)", 10, MUTED, "the #1's mid-season adaptation"),
        ("Boss's Orders x3, Night Stretcher x2, Dawn, Judge", 4, MUTED, "reach + recursion"),
    ]
    fig, ax = plt.subplots(figsize=(7.6, 3.6))
    left = 0
    for name, n, col, note in rows:
        ax.barh(0, n, left=left, color=col, height=0.4, edgecolor="white", lw=1.2)
        if n >= 3:
            ax.text(left + n/2, 0, str(n), ha="center", va="center", color="white",
                    fontsize=9, fontweight="bold")
        left += n
    y = -0.42
    for name, n, col, note in rows:
        ax.text(0.5, y, f"■", color=col, fontsize=9, va="center")
        ax.text(2.2, y, f"{name} — {note}", fontsize=7.8, va="center")
        y -= 0.16
    ax.set_xlim(0, 60); ax.set_ylim(-1.6, 0.5); ax.axis("off")
    title(ax, "Fig 7 — The submitted deck: the #1 player's current Dragapult 60", pad=8)
    footer(fig, "Reconstructed by serial aggregation (validated byte-exact on our own deck); tracks his mid-season rebuild (Jamming Tower + Latias ex in).")
    fig.savefig(OUT / "fig7_deck.png"); plt.close(fig)


# ---- FIG 8: ladder trajectory
def fig8():
    events = [
        ("rules bots\n(era floor)", 617, MUTED),
        ("first imitation\n(v2)", 760, NEUTRAL),
        ("v4/v6 fine-tunes", 914, NEUTRAL),
        ("v12 peak era", 1009, NEUTRAL),
        ("meta shifts;\nGrimmsnarl sinks", 764, LOSS),
        ("2nd-deck attempts\n(bugged era)", 649, LOSS),
        ("value-repaired\nbuilds", 687, ACCENT),
        ("DRAG v4\n(#1's corpus)", 890, WIN),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    x = np.arange(len(events))
    ys = [e[1] for e in events]
    ax.plot(x, ys, "-", color=MUTED, lw=1.2, zorder=2)
    for xi, (lab, y, col) in enumerate(events):
        ax.scatter([xi], [y], s=90, color=col, zorder=4, edgecolor="white", lw=1.2)
        ax.annotate(lab, (xi, y), textcoords="offset points",
                    xytext=(0, 14 if xi % 2 == 0 else -30), ha="center", fontsize=7.6)
        ax.text(xi, y - 28 if xi % 2 == 0 else y + 16, str(y), ha="center",
                fontsize=8, color=col, fontweight="bold")
    ax.set_xticks([]); ax.set_ylabel("ladder score")
    ax.set_ylim(520, 1120)
    title(ax, "Fig 8 — The campaign in ladder scores",
          "Note the shape: the peak-era 1009 and the 890 are different metas (the whole ladder deflated); "
          "the second rise is the audited pipeline paying out on a second archetype.")
    footer(fig, "Points are representative submissions; scores are era-local and not directly comparable across meta shifts.")
    fig.savefig(OUT / "fig8_trajectory.png"); plt.close(fig)


if __name__ == "__main__":
    for f in (fig1, fig2, fig3, fig4, fig5, fig6, fig7, fig8):
        f()
    print("wrote:")
    for p in sorted(OUT.glob("*.png")):
        print("  ", p.name, f"{p.stat().st_size//1024} KB")
