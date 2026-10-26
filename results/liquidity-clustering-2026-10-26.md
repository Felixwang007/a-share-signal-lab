# Liquidity floor vs. episode clustering — A-share oversold-bounce signal

Run date: 2026-10-26 (market close). Scripts: `clean_study_1026.py`, `bootstrap_1026.py`.

## Setup (point-in-time, no survivorship repair, no look-ahead)

- Universe: 3,184 A-shares whose last bar equals the market's last bar (2026-10-26).
  The raw local store had 3,487 files — 303 were stale tickers whose last bar was
  dated anywhere from 1994 to 2026-09. They are excluded, not patched.
- Bars: 641 daily qfq bars per stock (Tencent `fqkline`), sample window 2024-01-01 → 2026-10-26.
- Classified bars: 892,992. Each bar is assigned at most one of six patterns, in this
  precedence order: breakout → high-vol drop → oversold bounce → quiet pullback →
  uptrend → flat.
- Target: forward 5-day close-to-close return (`fwd5`), in %.
- Liquidity proxy: 20-day mean traded value = mean(volume_lots × 100 × close).

### Signal definitions (verbatim from the screener)

```
breakout        close > max(high[-20:-1]) and vr >= 1.5
high_vol_drop   pos20 >= 0.70 and chg <= -3.0 and vr >= 1.3
oversold_bounce ma5 < ma20 and c20 <= -15 and chg > 2.0 and vr >= 1.2
quiet_pullback  ma5 > ma20 and chg < 0 and vr <= 0.85
uptrend         ma5 > ma10 > ma20 and close > ma20
flat            (hi20-lo20)/lo20 < 8% and |chg| < 1.5
```
`vr` = today's volume / mean volume of the previous 5 bars; `pos20` = position of close
inside the 20-day close range; `c20` = 20-day return.

## All six patterns, 2024-01-01 → 2026-10-26

| pattern | n | mean fwd5 % | median % | win % |
|---|---:|---:|---:|---:|
| oversold_bounce | 6,548 | +1.372 | +0.814 | 54.8 |
| flat | 184,618 | +0.421 | +0.167 | 51.2 |
| quiet_pullback | 233,645 | +0.362 | -0.169 | 47.9 |
| uptrend | 400,049 | +0.282 | -0.336 | 46.5 |
| breakout | 60,759 | -0.353 | -1.379 | 40.8 |
| high_vol_drop | 7,373 | -1.352 | -2.234 | 38.7 |

Market baseline (all 592k bars with a 5-day forward window): 2024 +0.320, 2025 +0.794, 2026 -0.239 mean fwd5 %.

## Oversold bounce by liquidity bucket

| 20d traded value | n | mean % | median % | win % | net after 0.21% round-trip |
|---|---:|---:|---:|---:|---:|
| < 20M CNY | 86 | +2.263 | +1.390 | 54.7 | +2.053 |
| 20–50M | 593 | +1.701 | +1.020 | 56.2 | +1.491 |
| 50–100M | 1,095 | +1.657 | +1.083 | 58.4 | +1.447 |
| 100–300M | 2,097 | +1.113 | +0.742 | 54.2 | +0.903 |
| 300M–1B | 1,730 | +1.497 | +0.827 | 54.8 | +1.287 |
| ≥ 1B | 947 | +1.099 | +0.261 | 51.0 | +0.889 |

## The filter that looked good in one year

Liquidity + price floor = `amt20 >= 50M CNY` **and** `close >= 3 CNY`:

| window | base mean % | floored mean % | delta pp |
|---|---:|---:|---:|
| 2024 | +0.992 (n=1,432) | +0.456 (n=873) | **-0.536** |
| 2025 | +2.417 (n=2,042) | +2.329 (n=1,789) | -0.088 |
| 2026 | +0.864 (n=3,078) | +1.046 (n=2,773) | **+0.182** |
| all | +1.372 (n=6,548) | +1.378 (n=5,433) | **+0.006** |

## Why the per-year table lies: 6,548 signals are not 6,548 observations

- 32 months in the window; 11 months hold 84.7% of all signals.
- Top 10 months = 83.1% of signals; the largest two (2026-07 n=1,203, 2025-04 n=1,075) alone are 34.8%.
- Median month: ~65 signals. Signal-bearing months cluster around V-shaped rebounds.

Month-block bootstrap (10,000 resamples of *months*, seed 20261026):
point estimate **+0.006 pp**, 95% CI **[-0.223, +0.172]**, floor worse in **50.9%** of draws.

Conclusion recorded by the screener: the floor is not an improvement and not a
regression — it is unmeasurable on this sample, and the sign flip between 2024 and
2026 means it is a bet on tape, not a filter.

## What did change: signal frequency

| year | oversold signals | trading days | signals / day | excess over baseline |
|---|---:|---:|---:|---:|
| 2024 | 1,432 | 205 | 6.99 | +0.672 |
| 2025 | 2,042 | 243 | 8.40 | +1.623 |
| 2026 (to 10-26) | 3,078 | 194 | **15.87** | +1.103 |

2026-10 month to date: n=92, mean -4.98%, win 19.6%.

## Live scan, 2026-10-26 close

Pattern counts over the 3,184 live stocks: flat 335, uptrend 174, quiet_pullback 87,
breakout 66, oversold_bounce 16, high_vol_drop 4.

Universe gating matters: the same scan run over all 3,487 local files (ungated on
"last bar == market last bar") returns **50** oversold signals. 34 of those 50 are
bars from stocks that stopped trading months or years ago. Ghost rate: 68%.

Oversold signals surviving `amt20 >= 50M and close >= 3` (12):

| code | close | chg % | c20 % | vr | 20d traded value (M CNY) |
|---|---:|---:|---:|---:|---:|
| sh601086 | 11.47 | +2.41 | -35.1 | 1.99 | 913.5 |
| sh603011 | 19.69 | +5.01 | -27.4 | 1.99 | 602.3 |
| sh605179 | 20.75 | +3.08 | -24.0 | 1.75 | 417.6 |
| sz001331 | 35.02 | +9.99 | -24.1 | 2.02 | 314.5 |
| sz002903 | 25.62 | +4.79 | -18.7 | 1.44 | 228.2 |
| sz002943 | 24.19 | +3.60 | -22.1 | 2.03 | 221.4 |
| sz002829 | 16.80 | +2.88 | -18.1 | 1.43 | 115.0 |
| sz002289 | 31.00 | +3.85 | -15.3 | 1.64 | 113.5 |
| sz002973 | 10.60 | +4.74 | -18.3 | 1.21 | 102.3 |
| sh600962 | 22.59 | +3.15 | -16.4 | 1.21 | 98.7 |
| sz003041 | 34.64 | +2.12 | -19.9 | 1.22 | 88.2 |
| sz000586 | 11.45 | +2.69 | -19.2 | 1.39 | 76.3 |

Not investment advice. The measured claim is about the *screener*, not about these names.
