# -*- coding: utf-8 -*-
"""
volume-followthrough-study
==========================
Does "volume confirmation" predict the NEXT day in Chinese A-shares?

Data: daily OHLCV bars for 584 liquid A-share names (Shanghai + Shenzhen),
pulled from free public endpoints (Sina / Tencent quote APIs) — no API key,
no paid data vendor. 15,900 stock-days, June 2026 -> early September 2026
(the bulk is June + July).

Run:  python study.py path/to/bars.json

bars.json format:
{
  "daily_history": {
     "600519": [{"date":"2026-06-05","open":..,"high":..,"low":..,"close":..,"volume":..}, ...],
     ...
  },
  "stocks": {"600519": {"name": "..."}}
}

Everything printed below is computed from that file. No synthetic data.

WHAT IT PRINTS
  1. baseline next-day return of the whole sample
  2. next-day return conditioned on today's move
  3. next-day return conditioned on volume ratio (today's volume / 5-day avg)
  4. the cross of (move x volume ratio)
  5. the same buckets split by calendar month  <-- the interesting part
"""
import json
import sys
import statistics as st
from collections import Counter, defaultdict


def load(path):
    d = json.load(open(path, encoding="utf-8"))
    hist = d["daily_history"]
    names = {c: v.get("name", "") for c, v in d.get("stocks", {}).items()}
    return hist, names


def build_rows(hist):
    """One row per stock-day: (code, date, today_ret, volume_ratio, next_day_ret)."""
    rows = []
    for code, bars in hist.items():
        bars = sorted(bars, key=lambda x: x["date"])
        if len(bars) < 20:
            continue
        for i in range(6, len(bars) - 1):          # need 5 prior vols + 1 forward bar
            b, p = bars[i], bars[i - 1]
            if not p["close"] or not b["close"]:
                continue
            vols = [x["volume"] for x in bars[i - 5:i]]
            if len(vols) < 5:
                continue
            avg5 = sum(vols) / 5.0
            if avg5 <= 0:
                continue
            rows.append((
                code,
                b["date"],
                b["close"] / p["close"] - 1.0,      # today
                b["volume"] / avg5,                 # volume ratio
                bars[i + 1]["close"] / b["close"] - 1.0,   # tomorrow
            ))
    return rows


def describe(sel):
    if not sel:
        return None
    nx = [r[4] for r in sel]
    return {
        "n": len(sel),
        "mean": st.mean(nx) * 100,
        "median": st.median(nx) * 100,
        "win": sum(1 for x in nx if x > 0) / len(nx) * 100,
    }


def fmt(label, s):
    if not s:
        return f"{label:<34} n=0"
    return (f"{label:<34} n={s['n']:>6}  next-day mean={s['mean']:+.3f}%  "
            f"median={s['median']:+.3f}%  win={s['win']:.1f}%")


MOVE_BUCKETS = [
    (-1.0, -0.03, "down >3%"),
    (-0.03, -0.01, "down 1-3%"),
    (-0.01, 0.01, "flat +/-1%"),
    (0.01, 0.03, "up 1-3%"),
    (0.03, 0.095, "up 3-9.5%"),
    (0.095, 1.0, "limit-up >9.5%"),
]
VOL_BUCKETS = [
    (0.0, 0.7, "vol <0.7x  (dry)"),
    (0.7, 1.3, "vol 0.7-1.3x (normal)"),
    (1.3, 2.0, "vol 1.3-2x (mild)"),
    (2.0, 3.0, "vol 2-3x   (spike)"),
    (3.0, 99.0, "vol >3x    (huge)"),
]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "bars.json"
    hist, names = load(path)
    rows = build_rows(hist)

    print(f"stock-days: {len(rows)}   names: {len(hist)}")
    print(f"range: {min(r[1] for r in rows)} -> {max(r[1] for r in rows)}")
    print(f"coverage by month: {dict(sorted(Counter(r[1][:7] for r in rows).items()))}")

    print("\n[1] BASELINE (all stock-days)")
    print("   " + fmt("everything", describe(rows)))

    print("\n[2] BY TODAY'S MOVE")
    for lo, hi, lbl in MOVE_BUCKETS:
        print("   " + fmt(lbl, describe([r for r in rows if lo <= r[2] < hi])))

    print("\n[3] BY VOLUME RATIO (all days)")
    for lo, hi, lbl in VOL_BUCKETS:
        print("   " + fmt(lbl, describe([r for r in rows if lo <= r[3] < hi])))

    print("\n[4] MOVE x VOLUME RATIO")
    for mlo, mhi, mlbl in [(-1, -0.03, "down >3%"), (-0.03, 0.03, "flat"),
                           (0.03, 0.095, "up 3-9.5%")]:
        for vlo, vhi, vlbl in VOL_BUCKETS:
            sel = [r for r in rows if mlo <= r[2] < mhi and vlo <= r[3] < vhi]
            print("   " + fmt(f"{mlbl:<10} {vlbl}", describe(sel)))

    print("\n[5] SAME BUCKETS, SPLIT BY MONTH  <-- the regime test")
    setups = [
        ("limit-up >=9.5%",       lambda r: r[2] >= 0.095),
        ("up 3-9.5%, vol >=2x",   lambda r: 0.03 <= r[2] < 0.095 and r[3] >= 2),
        ("up 3-9.5%, vol 1.3-2x", lambda r: 0.03 <= r[2] < 0.095 and 1.3 <= r[3] < 2),
        ("up 3-9.5%, vol <1.3x",  lambda r: 0.03 <= r[2] < 0.095 and r[3] < 1.3),
        ("flat, vol <0.7x",       lambda r: abs(r[2]) < 0.03 and r[3] < 0.7),
        ("down >3%, vol <0.7x",   lambda r: r[2] <= -0.03 and r[3] < 0.7),
        ("down >3%, vol >=2x",    lambda r: r[2] <= -0.03 and r[3] >= 2),
    ]
    months = sorted({r[1][:7] for r in rows})
    hdr = f"{'setup':<24}" + "".join(f"{m:>18}" for m in months) + "   stable?"
    print("   " + hdr)
    for lbl, f in setups:
        cells, signs = [], []
        for m in months:
            s = describe([r for r in rows if r[1][:7] == m and f(r)])
            if s and s["n"] >= 5:
                cells.append(f"{s['mean']:+6.2f}%/{s['win']:4.1f}%")
                signs.append(1 if s["mean"] > 0 else -1)
            else:
                cells.append("       n/a      ")
        stable = len(set(signs)) == 1 and len(signs) >= 2
        print("   " + f"{lbl:<24}" + "".join(f"{c:>18}" for c in cells)
              + ("   YES" if stable else "   flips"))

    print("\n[6] EXCESS OVER MARKET DRIFT")
    print("   a setup's edge is (its mean) - (equal-weighted market drift that month)")
    print(f"   {'setup':<24}{'month':>9}{'n':>7}{'setup':>9}{'drift':>9}{'excess':>10}")
    for lbl, f in setups:
        for m in months:
            base = [r for r in rows if r[1][:7] == m]
            sel = [r for r in base if f(r)]
            if len(sel) < 5 or not base:
                continue
            D = st.mean([r[4] for r in base]) * 100
            M = st.mean([r[4] for r in sel]) * 100
            print(f"   {lbl:<24}{m:>9}{len(sel):>7}{M:>+8.2f}%{D:>+8.3f}%{M - D:>+9.2f}pp")


if __name__ == "__main__":
    main()
