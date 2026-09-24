#!/usr/bin/env python3
"""A free A-share breadth gauge + a date-clustered signal study.

Input : ./history_ext/*.json  — one file per stock, daily bars
        (built by download_history_qq.py from the free Tencent quote endpoint
         https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600000,day,,,640,qfq)
Output: breadth_gauge.json   — per trading day: % of stocks above MA20, % up, equal-weight return
        breadth_rows.json    — every pattern-labelled stock-day + its forward 5-day return
        breadth_stats.json   — the clustered statistics printed below

Two measurement corrections that this script exists to make, both of which flip conclusions:

  1. RAGGED PANEL. Concatenating per-stock files produces "dates" on which a single
     stock traded (stale/delisted files). Here 6,487 dates appear in the raw rows but
     only 622 are real market days (>=500 stocks with a 20-day MA). Averaging over the
     phantom dates is what made an "uptrend" pattern look like t=+5.7 (it is t=+1.5).

  2. DATE CLUSTERING. Stock-days inside one session are highly correlated: a market-wide
     bounce lifts hundreds of "oversold rebound" names at once. Every statistic below is
     therefore computed as a mean of PER-DAY means, and t uses the number of DAYS.

Usage:  python breadth_gauge.py [history_ext_dir]
"""
import json, os, sys, glob, statistics as st
from collections import defaultdict

SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'history_ext')
OUT = os.path.dirname(os.path.abspath(__file__))

SIGS = ['OversoldRebound', 'LowVolPullback', 'Uptrend', 'Sideways',
        'Breakout+Volume', 'HighLevelVolumeDrop']
BUCKETS = [(-1, 20, '<20'), (20, 40, '20-40'), (40, 60, '40-60'),
           (60, 80, '60-80'), (80, 101, '>80')]


def signal_of(closes, highs, lows, vols, i):
    """Pattern rules, ported verbatim from the model training set builder
    so that labels here and labels in stock_training_data_v3.jsonl agree
    (verified: 5,998 / 6,000 labelled rows reproduce, 99.97%)."""
    close, prev_close = closes[i], closes[i - 1]
    op, hi, lo = closes[i], highs[i], lows[i]
    vol = vols[i]
    if close <= 0 or prev_close <= 0 or hi <= lo:
        return None
    wc = closes[i - 19:i + 1]
    ma5, ma10, ma20 = st.fmean(wc[-5:]), st.fmean(wc[-10:]), st.fmean(wc)
    v5 = st.fmean(vols[i - 5:i]) if i >= 5 else vol
    vr = vol / v5 if v5 > 0 else 1.0
    hi20, lo20 = max(wc), min(wc)
    pos = (close - lo20) / (hi20 - lo20) if hi20 > lo20 else 0.5
    prev_hi20 = max(highs[i - 19:i])
    c20 = (close / wc[0] - 1) * 100
    chg = (close - prev_close) / prev_close * 100
    if close > prev_hi20 and vr >= 1.5:
        return 'Breakout+Volume'
    if pos >= 0.70 and chg <= -3.0 and vr >= 1.3:
        return 'HighLevelVolumeDrop'
    if ma5 < ma20 and c20 <= -15 and chg > 2.0 and vr >= 1.2:
        return 'OversoldRebound'
    if ma5 > ma20 and chg < 0 and vr <= 0.85:
        return 'LowVolPullback'
    if ma5 > ma10 > ma20 and close > ma20:
        return 'Uptrend'
    if (hi20 - lo20) / lo20 * 100 < 8 and abs(chg) < 1.5:
        return 'Sideways'
    return None


def build():
    files = sorted(glob.glob(os.path.join(SRC, '*.json')))
    daily = defaultdict(lambda: dict(above=0, tot=0, up=0, chgs=[]))
    rows = []
    for fi, fp in enumerate(files):
        code = os.path.basename(fp)[:-5]
        try:
            df = json.load(open(fp, encoding='utf-8'))
        except Exception:
            continue
        closes = [float(x['close']) for x in df]
        highs = [float(x['high']) for x in df]
        lows = [float(x['low']) for x in df]
        vols = [float(x['volume']) for x in df]
        dates = [x['date'] for x in df]
        n = len(closes)
        for i in range(19, n):
            ma20 = st.fmean(closes[i - 19:i + 1])
            d = daily[dates[i]]
            d['tot'] += 1
            if closes[i] > ma20:
                d['above'] += 1
            if closes[i - 1] > 0:
                c = (closes[i] / closes[i - 1] - 1) * 100
                d['chgs'].append(c)
                if c > 0:
                    d['up'] += 1
            if i < 20 or i + 5 >= n:
                continue
            sig = signal_of(closes, highs, lows, vols, i)
            if sig:
                rows.append(dict(code=code, date=dates[i], sig=sig,
                                 fwd5=round((closes[i + 5] / closes[i] - 1) * 100, 2)))
        if (fi + 1) % 500 == 0:
            print(f'  ...{fi+1}/{len(files)} stocks', flush=True)

    series = []
    for date in sorted(daily):
        d = daily[date]
        if d['tot'] < 500:                      # correction #1: keep real market days only
            continue
        series.append(dict(date=date, n=d['tot'],
                           above_ma20=round(100 * d['above'] / d['tot'], 2),
                           up_pct=round(100 * d['up'] / max(1, len(d['chgs'])), 2),
                           mean_chg=round(st.fmean(d['chgs']), 2) if d['chgs'] else 0.0))
    json.dump(series, open(os.path.join(OUT, 'breadth_gauge.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    json.dump(rows, open(os.path.join(OUT, 'breadth_rows.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print(f'stocks={len(files)}  market_days={len(series)}  labelled_rows={len(rows):,}')
    return series, rows


def cluster(per_day_values):
    """correction #2: one observation per day"""
    pd_ = [st.fmean(v) for v in per_day_values]
    m = st.fmean(pd_)
    sd = st.stdev(pd_)
    return dict(days=len(pd_), mean=round(m, 3), t=round(m / (sd / len(pd_) ** 0.5), 2))


def stats(series, rows):
    bmap = {s['date']: s['above_ma20'] for s in series}
    eq = [100.0]
    for s in series[1:]:
        eq.append(eq[-1] * (1 + s['mean_chg'] / 100))
    ufwd = {s['date']: (eq[i + 5] / eq[i] - 1) * 100
            for i, s in enumerate(series) if i + 5 < len(series)}
    by = defaultdict(list)
    naive = defaultdict(list)
    for r in rows:
        naive[r['sig']].append(r['fwd5'])
        if r['date'] in bmap:
            by[(r['sig'], r['date'])].append(r['fwd5'])
    out = {'per_signal': {}, 'per_signal_naive': {}, 'cells': {},
           'cells_excess': {}, 'timing': {}, 'latest': series[-1],
           'span': f"{series[0]['date']}..{series[-1]['date']}", 'market_days': len(series)}
    print('\nsignal                    days    rows    clustered fwd5      t     naive')
    for s in SIGS:
        c = cluster([v for (sg, d), v in by.items() if sg == s])
        n = sum(len(v) for (sg, d), v in by.items() if sg == s)
        out['per_signal'][s] = dict(rows=n, **c)
        out['per_signal_naive'][s] = round(st.fmean(naive[s]), 3)
        print(f'{s:<22}{c["days"]:>5} {n:>8,}   {c["mean"]:+7.3f}%  {c["t"]:+6.2f}   {st.fmean(naive[s]):+7.3f}%')
    print('\nsignal x breadth (mean of per-day means, fwd 5d)')
    print('signal'.ljust(22) + ''.join(b[2].rjust(16) for b in BUCKETS))
    for s in SIGS:
        line = s.ljust(22)
        for lo, hi, lab in BUCKETS:
            pairs = [v for (sg, d), v in by.items() if sg == s and lo < bmap[d] <= hi]
            if len(pairs) < 5:
                line += '-'.rjust(16); continue
            c = cluster(pairs)
            out['cells'][f'{s}|{lab}'] = c
            line += f'{c["mean"]:+.2f}% t{c["t"]:+.1f}'.rjust(16)
        print(line)
    print('\nexcess over the equal-weight universe (row fwd5 minus same-day universe fwd5)')
    xs = defaultdict(list)
    for r in rows:
        d = r['date']
        if d in ufwd:
            xs[(r['sig'], d)].append(r['fwd5'] - ufwd[d])
    for s in SIGS:
        c = cluster([v for (sg, d), v in xs.items() if sg == s])
        out['cells_excess'][s] = c
        print(f'  {s:<22} {c["mean"]:+.3f}%  t {c["t"]:+.2f}  days {c["days"]}')
    print('\nbreadth bucket -> next-5d equal-weight return')
    for lo, hi, lab in BUCKETS:
        v = [ufwd[s['date']] for s in series if lo < s['above_ma20'] <= hi and s['date'] in ufwd]
        m = st.fmean(v); sd = st.stdev(v)
        out['timing'][lab] = dict(days=len(v), mean=round(m, 2), t=round(m / (sd / len(v) ** 0.5), 2),
                                  up_days=round(100 * sum(1 for x in v if x > 0) / len(v), 1))
        print(f"  {lab:>6}  {len(v):>4} days  {m:+.2f}%  t {out['timing'][lab]['t']:+.2f}  "
              f"up-days {out['timing'][lab]['up_days']}%")
    json.dump(out, open(os.path.join(OUT, 'breadth_stats.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('\nwrote breadth_gauge.json / breadth_rows.json / breadth_stats.json')


if __name__ == '__main__':
    stats(*build())
