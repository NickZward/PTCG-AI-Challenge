#!/bin/bash
# Crash-resilient round-robin driver: one python process per pair, so a native crash in the
# cg engine loses one pair, not the tournament. Appends to the log; skips pairs already done.
cd /Users/nickzwart/Desktop/PTCG-AI-Challenge
LOG="$1"; N="$2"; shift 2
AGENTS=("$@")
for ((i=0; i<${#AGENTS[@]}; i++)); do
  for ((j=i+1; j<${#AGENTS[@]}; j++)); do
    A="${AGENTS[$i]}"; B="${AGENTS[$j]}"
    TAG="$(basename "$A") vs $(basename "$B")"
    if grep -qF "$TAG" "$LOG" 2>/dev/null; then echo "skip: $TAG"; continue; fi
    OUT=$(python3 analysis/round_robin.py "$N" "$A" "$B" 2>&1 | grep " vs " | head -1)
    if [ -n "$OUT" ]; then echo "$OUT" >> "$LOG"; echo "done: $OUT"
    else echo "PAIR-CRASH: $TAG" >> "$LOG"; echo "PAIR-CRASH: $TAG"; fi
  done
done
echo "ALL PAIRS COMPLETE" >> "$LOG"
