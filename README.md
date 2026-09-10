# Does "volume confirmation" predict the next day in Chinese A-shares?

An honest replication attempt on **15,900 real stock-days** (584 liquid Shanghai/Shenzhen
names, June 2026 → early September 2026, bulk = June + July), using free public quote
endpoints — no API key, no paid data vendor.

Short answer: **the setup did not carry a stable edge. It flipped sign between two
consecutive months, and its size scaled with the market's own drift.** If you learn a
"rule" from one month of A-share data, you have learned that month, not the rule.

## Method

For every stock-day `t` with at least 5 prior bars and one forward bar:

| field | definition |
|---|---|
| `today` | `close[t] / close[t-1] - 1` |
| `vr` | `volume[t] / mean(volume[t-5 .. t-1])` — volume ratio vs 5-day average |
| `next` | `close[t+1] / close[t] - 1` — what we are trying to predict |

Then bucket by `today` and by `vr`, and report next-day mean / median / win-rate.
Finally, split every bucket by calendar month — that split is the whole point.

## Baseline

```
everything   n=15900   next-day mean=-0.063%   median=-0.123%   win=47.3%
```

The sample window drifts slightly down. Hold on to that number — it is the yardstick for
every "signal" below.

## Conditioned on today's move

```
down >3%          n= 2330   mean=-0.184%   win=45.8%
down 1-3%         n= 3530   mean=+0.110%   win=49.5%
flat +/-1%        n= 4743   mean=-0.061%   win=47.5%
up 1-3%           n= 3162   mean=-0.192%   win=46.0%
up 3-9.5%         n= 1797   mean=-0.260%   win=44.8%
limit-up >9.5%    n=  338   mean=+1.199%   win=56.5%
```

Only limit-ups show positive follow-through in aggregate — and even that, see the monthly
split below, is not a law.

## Conditioned on volume ratio

```
vol <0.7x   (dry)     n= 2293   mean=-0.121%   win=45.3%
vol 0.7-1.3x (normal) n=10852   mean=-0.050%   win=47.7%
vol 1.3-2x  (mild)    n= 2291   mean=-0.099%   win=46.7%
vol 2-3x    (spike)   n=  371   mean=+0.168%   win=50.4%
vol >3x     (huge)    n=   93   mean=-0.169%   win=48.4%
```

Volume alone is almost information-free here. "Huge volume" is not bullish.

## The cross: move × volume

```
up 3-9.5%   vol <0.7x     n=   37   mean=-0.295%   win=37.8%
up 3-9.5%   vol 0.7-1.3x  n=  828   mean=-0.560%   win=42.5%
up 3-9.5%   vol 1.3-2x    n=  709   mean=-0.049%   win=46.4%
up 3-9.5%   vol 2-3x      n=  187   mean=+0.346%   win=50.8%
up 3-9.5%   vol >3x       n=   36   mean=-0.617%   win=41.7%
```

This is the most-quoted version of the rule: *a big up day on weak volume fails, a big up
day on strong volume continues.* In aggregate the data agrees — the weak-volume bucket is
the second-worst in the entire study and it is **5.4% of all stock-days** (865 samples),
i.e. it is the thing retail traders most often buy.

But now split it by month.

## The regime test — same setup, two months

```
setup                    2026-06          2026-07          2026-08    stable?
limit-up >=9.5%        +2.18%/64.2%     -1.39%/35.6%     +5.46%/100%    flips
up 3-9.5%, vol >=2x    +0.48%/52.0%     -0.33%/44.2%     +2.32%/71.4%   flips
up 3-9.5%, vol 1.3-2x  +0.43%/52.6%     -0.71%/37.7%     +0.69%/52.6%   flips
up 3-9.5%, vol <1.3x   +0.18%/50.2%     -1.43%/32.5%     -0.61%/42.9%   flips
flat, vol <0.7x        -0.12%/44.8%     -0.17%/45.4%     +0.52%/52.8%   flips
down >3%, vol <0.7x    +0.01%/53.4%     -1.15%/33.9%     +0.57%/60.0%   flips
down >3%, vol >=2x     +0.60%/46.2%     -1.24%/36.8%         n/a        flips
```

**Every single setup flips.** The most dramatic: limit-up follow-through was +2.18% with a
64% win rate in June and −1.39% with a 36% win rate in July — same rule, same market, one
month apart. A trader who "validated" the rule in June and sized up in July would have paid
for the education in full.

## Excess over market drift

A setup's edge should be measured net of whatever the market itself did that month:

```
setup                   month      n    setup    drift    excess
limit-up >=9.5%        2026-06    229   +2.18%  +0.049%    +2.13pp
limit-up >=9.5%        2026-07    101   -1.39%  -0.236%    -1.15pp
up 3-9.5%, vol >=2x    2026-06    127   +0.48%  +0.049%    +0.43pp
up 3-9.5%, vol >=2x    2026-07     86   -0.33%  -0.236%    -0.09pp
up 3-9.5%, vol <1.3x   2026-06    462   +0.18%  +0.049%    +0.13pp
up 3-9.5%, vol <1.3x   2026-07    369   -1.43%  -0.236%    -1.20pp
down >3%, vol <0.7x    2026-06    103   +0.01%  +0.049%    -0.04pp
down >3%, vol <0.7x    2026-07    174   -1.15%  -0.236%    -0.91pp
```

The excess flips too — and it flips *harder* than the drift. These setups are not
independent alpha; they are **amplifiers of the current market regime**. When the tape's
next-day drift is positive, momentum setups magnify it; when it is negative, they magnify
the loss. Magnitude ratios in this sample: 1.4× to 6× the baseline drift.

## What actually holds up

1. **Measure net of drift, or don't measure at all.** A monthly equal-weighted next-day
   mean is one line of code and it removes the single largest source of fake "edge".
2. **Require the *excess* to keep its sign across at least two regimes** before risking
   money on it. In this sample that filter kills all seven setups — which is the correct
   output of an honest test, not a failure of the test.
3. **Sample size does not save you.** The buckets with the most samples (10,852 normal-volume
   days, 8,219 flat days) are the ones closest to the baseline. The buckets with the biggest
   headline numbers have the smallest n. n=93 "huge volume" days can produce any story you want.
4. **The most reliable line in the whole dataset is the baseline**: 47.3% win rate, negative
   mean. In a flat-to-down tape most aggressive entries have negative expectancy *before*
   costs and before A-share T+1 constraints, which this study does not model.

## Caveats (read these)

- 584 liquid, mostly well-known names — not the full ~5,200-stock market. Microcaps and
  newly listed names are not represented.
- Four months of data, heavily weighted to June–July. August/September buckets are shown
  but their n is tiny (5–36); do not read them as evidence.
- No transaction costs, no slippage, no T+1 executability check, no limit-up fill
  assumption. A signal that cannot be filled is not a signal.
- Volume ratio uses a 5-day average; different windows will produce different buckets.
- Overlapping windows: consecutive stock-days are not independent, so effective sample size
  is lower than the n shown. No significance testing is claimed anywhere.

## Run it

```bash
python study.py bars.json
```

`bars.json` needs `daily_history` (per-code list of `{date,open,high,low,close,volume}`) and
optionally `stocks` for names. Free sources that work without a key: Sina
`vip.stock.finance.sina.com.cn` market-center endpoints for snapshots, Tencent
`web.ifzq.gtimg.cn/appstock/app/fqkline/get` for daily K-lines.
