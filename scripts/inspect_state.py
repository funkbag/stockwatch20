#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

STATE = Path(__file__).resolve().parents[1] / "data" / "state.json"

if not STATE.exists():
    raise SystemExit(f"State file not found: {STATE}")

state = json.loads(STATE.read_text())
items = state.get("items", [])
errors = [x for x in items if x.get("error")]

print(f"Updated:    {state.get('updated_at')}")
print(f"Configured: {len(state.get('watchlist', []))}")
print(f"Analysed:   {len(items)}")
print(f"Errors:     {len(errors)}")
print()
print(f"{'Ticker':<7} {'Score':>6} {'Delta':>7}  {'Label':<15} {'Early alert'}")
print("-" * 72)
for item in items:
    signal = item.get("signal", {})
    alert = item.get("technical_alert", {})
    delta = signal.get("score_change")
    delta_txt = "—" if delta is None else f"{delta:+.1f}"
    print(
        f"{item.get('symbol','?'):<7} "
        f"{signal.get('score',0):>+6} "
        f"{delta_txt:>7}  "
        f"{signal.get('label','NO DATA'):<15} "
        f"{alert.get('label','—')}"
    )

if errors:
    print("\nErrors:")
    for item in errors:
        print(f"- {item.get('symbol')}: {item.get('error')}")
