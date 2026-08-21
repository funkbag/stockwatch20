# Signal methodology

StockWatch is a heuristic research system. It combines multiple weak/medium indicators rather than treating any one technical theory as deterministic.

## Price inputs

For each configured symbol:

- Intraday structure: approximately one month of 1-hour bars, including pre/post-market where available.
- Daily structure: up to one year of daily bars, unless `history_start` explicitly limits history.
- Relative-strength benchmark: six months of daily data for the configured benchmark (default `SPY`).

Prices are requested with `auto_adjust=True`.

## Technical snapshot

The engine calculates:

- EMA20, EMA50, EMA200 on hourly closes.
- RSI(14) using exponentially weighted gains/losses.
- MACD = EMA12 - EMA26 and 9-period signal line.
- ATR(14) and ATR as percentage of current price.
- Volume Z-score versus the recent 30 hourly observations.
- Distance from the 20-day high and low.
- 20-day return relative to the benchmark.

## Fibonacci

The current implementation finds the high and low in the latest 90 daily closes and determines swing direction from which endpoint occurred first. It produces retracement levels at:

```text
0.236, 0.382, 0.500, 0.618, 0.786
```

These are reference levels, not probability estimates.

## Elliott heuristic

A simple 5% ZigZag identifies recent swing pivots. The engine cautiously classifies alternating pivots as one of:

- bullish 5-wave candidate,
- bearish 5-wave candidate,
- ABC / complex correction candidate,
- mixed / corrective,
- insufficient structure.

Elliott classification intentionally receives only a small contribution to the composite score because automated wave counts are highly subjective.

## Headline sentiment and catalysts

The latest configured number of Yahoo Finance headlines is scored with VADER compound sentiment.

A lightweight keyword classifier additionally flags positive and negative catalyst terms such as upgrades, approvals, contracts, offerings, dilution, investigations, guidance changes, trial outcomes, and delisting risk.

This is headline-level sentiment only; it does not read or reason over full articles.

## Composite score

The score is clamped to `-100 ... +100`.

Main contributions include:

- EMA trend alignment.
- Price relative to EMA200.
- RSI regime.
- MACD relationship.
- abnormal volume in the direction of the latest hourly move.
- proximity to the 20-day high.
- benchmark-relative strength.
- low-weight Elliott heuristic.
- mean headline sentiment and catalyst balance.

Labels are assigned as:

```text
score >= +55  BULLISH ALERT
score >= +25  BULLISH WATCH
-24..+24      NEUTRAL
score <= -25  BEARISH WATCH
score <= -55  BEARISH ALERT
```

## Score movement

Each scan reads the prior persisted `state.json` and stores:

```text
previous_score
score_change = current_score - previous_score
```

Dashboard movement classes are:

```text
score_change >= +10    FAST IMPROVING
-9.9 .. +9.9           STABLE
score_change <= -10    FAST DETERIORATING
```

The first scan has no prior comparison and is treated as stable in the UI.

## Technical Early Alert

The deterministic early-alert engine is separate from the composite label. It accumulates bullish and bearish points from:

- absolute composite-score regime,
- score acceleration/deterioration of at least 10 points,
- volume Z-score >= 2 in the direction of price movement,
- 1-hour movement relative to ATR,
- proximity to 20-day high/low,
- relative strength/weakness versus benchmark,
- headline sentiment/catalyst balance,
- composite-label changes.

An early alert becomes active when directional strength reaches the internal materiality threshold. Stronger setups or absolute composite scores beyond the alert threshold become `BULLISH TRIGGER` or `BEARISH TRIGGER`; otherwise they are `EARLY BULLISH SETUP` or `EARLY BEARISH SETUP`.

### Confirmation and invalidation

The engine builds candidate levels from EMA20/50/200, Fibonacci levels, and reconstructed 20-day high/low levels.

For bullish setups it selects nearby resistance as confirmation and nearby support as invalidation. For bearish setups this logic is reversed. If no suitable structure level exists, ATR-based fallback levels are used.

## Alert history

A new history item is stored only for a material transition, such as:

- inactive -> active,
- setup/trigger label changes,
- direction changes,
- confidence change >= 10 points,
- unusually strong score acceleration.

History is bounded to the latest 20 entries per ticker so `state.json` remains small.

## Limitations

- This is not a backtested trading strategy.
- Headline sentiment is lexicon-based and can misread context, sarcasm, legal language, or complex corporate events.
- Elliott-wave labels are intentionally approximate.
- Fibonacci levels are descriptive reference points.
- The current data adapter is not suitable as-is for institutional-grade market-data requirements.
- Scores are not calibrated probabilities of future return.
