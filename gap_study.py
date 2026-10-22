#!/usr/bin/env python3
"""Do gap-ups in Chinese A-shares follow through?

Measures ~1.9M main-board stock-days (2024-02 .. latest bar in your data) for:

  1. gap size  -> next-day / 5-day forward return
  2. gap size x volume ratio (volume / 20-day average) -> next-day / 5-day
  3. gap-downs (knife-catching check)
  4. the fat-tail check: is the mean or the median the honest number?

Usage:
    python gap_study.py [history_dir] [--markdown]

history_dir holds one JSON per stock: [{"date","code","open","close","high","low","volume"}, ...]
(prices must be split/dividend adjusted — qfq). Names file `stock_names.json`
({"sh600000": "浦发银行", ...}) is optional; when present, ST / delisting names are dropped.

No API calls, no keys. Feed it whatever adjusted daily bars you have.
"""
import json, os, sys, statistics as st
from collections import defaultdict

UPB = [(0.02, 0.03, 'A +2~3%'), (0.03, 0.05, 'B +3~5%'),
       (0.05, 0.09, 'C +5~9%'), (0.09, 9.9, 'D >=9% (limit-up gap)')]
DNB = [(-0.03, -0.02, 'a -3~-2%'), (-0.05, -0.03, 'b -5~-3%'), (-9.9, -0.05, 'c <=-5%')]
VOLD = [(0, 1, 'V1 vr<1'), (1, 2, 'V2 1-2'), (2, 3, 'V3 2-3'), (3, 999, 'V4 vr>3')]
BAD_NAMES = ('退', 'ST', '*')


def tag(v, table):
    for lo, hi, lab in table:
        if lo <= v < hi:
            return lab
    return None


def pctile(xs, p):
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summ(xs, min_n=40):
    if len(xs) < min_n:
        return None
    return {'n': len(xs), 'mean_pct': round(100 * st.mean(xs), 3),
            'median_pct': round(100 * st.median(xs), 3),
            'win_pct': round(100 * sum(1 for x in xs if x > 0) / len(xs), 1)}


def load_names(hist):
    for cand in (os.path.join(os.path.dirname(hist), 'stock_names.json'),
                 os.path.join(hist, 'stock_names.json')):
        if os.path.exists(cand):
            try:
                raw = json.load(open(cand, encoding='utf-8'))
                return {k.replace('sh', '').replace('sz', ''): v for k, v in raw.items()}
            except Exception:
                pass
    return {}


def main():
    hist = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('-') else 'history_ext'
    md = '--markdown' in sys.argv
    nmap = load_names(hist)
    files = [f for f in os.listdir(hist) if f.endswith('.json') and f[0].isdigit()]
    up, up5, dn, dn5 = (defaultdict(list) for _ in range(4))
    cross, cross5 = defaultdict(list), defaultdict(list)
    base = {'next1': [], 'fwd5': []}
    dist = {'C_lowvol': [], 'C_highvol': [], 'B_lowvol': [], 'D_limit': []}
    latest = {}
    today = {'total': 0, 'gapup': 0, 'faded': 0, 'filled': 0}
    used = 0
    last_bar = ''

    for fn in files:
        code = fn[:-5]
        nm = nmap.get(code, '')
        if nm and any(b in nm for b in BAD_NAMES):
            continue
        try:
            bars = json.load(io.open(os.path.join(hist, fn), encoding='utf-8'))
        except Exception:
            continue
        if len(bars) < 60:
            continue
        used += 1
        o = [float(b['open']) for b in bars]
        c = [float(b['close']) for b in bars]
        lo = [float(b['low']) for b in bars]
        v = [float(b['volume']) for b in bars]
        n = len(bars)
        last_bar = bars[-1]['date']
        for i in range(21, n):
            pc, op, cl = c[i - 1], o[i], c[i]
            if pc <= 0 or op <= 0 or cl <= 0:
                continue
            gap = op / pc - 1.0
            nxt = (c[i + 1] / cl - 1.0) if i + 1 < n else None
            f5 = (c[i + 5] / cl - 1.0) if i + 5 < n else None
            if nxt is not None:
                base['next1'].append(nxt)
            if f5 is not None:
                base['fwd5'].append(f5)
            prev = v[i - 20:i]
            avgv = sum(prev) / len(prev) if prev else 0
            vr = (v[i] / avgv) if avgv > 0 else None

            b = tag(gap, UPB)
            if b:
                if nxt is not None:
                    up[b].append(nxt)
                if f5 is not None:
                    up5[b].append(f5)
                if vr is not None and gap < 0.09:
                    vb = tag(vr, VOLD)
                    if vb:
                        if nxt is not None:
                            cross[(b, vb)].append(nxt)
                        if f5 is not None:
                            cross5[(b, vb)].append(f5)
                if f5 is not None and vr is not None:
                    if 0.05 <= gap < 0.09 and vr < 1:
                        dist['C_lowvol'].append(f5)
                    elif 0.05 <= gap < 0.09 and vr > 3:
                        dist['C_highvol'].append(f5)
                    elif 0.03 <= gap < 0.05 and vr < 1:
                        dist['B_lowvol'].append(f5)
                if f5 is not None and gap >= 0.09:
                    dist['D_limit'].append(f5)
            b = tag(gap, DNB)
            if b:
                if nxt is not None:
                    dn[b].append(nxt)
                if f5 is not None:
                    dn5[b].append(f5)
            if i == n - 1:
                today['total'] += 1
                if gap >= 0.02:
                    today['gapup'] += 1
                    today['faded'] += 1 if cl < op else 0
                    today['filled'] += 1 if lo[i] <= pc else 0
                    if len(latest) < 12:
                        latest[code] = {'name': nm, 'gap': round(gap * 100, 2),
                                        'day': round((cl / pc - 1) * 100, 2)}

    def cell_table(src):
        rows = {}
        for k, xs in sorted(src.items()):
            s = summ(xs)
            if s:
                rows[k if isinstance(k, str) else ' | '.join(k)] = s
        return rows

    dsum = {}
    for k, xs in dist.items():
        if not xs:
            continue
        s = sorted(xs)
        top5 = s[int(len(s) * 0.95):]
        tot = sum(xs)
        dsum[k] = {'n': len(xs), 'mean_pct': round(100 * st.mean(xs), 3),
                   'median_pct': round(100 * st.median(xs), 3),
                   'p25': round(100 * pctile(xs, 25), 3),
                   'p75': round(100 * pctile(xs, 75), 3),
                   'p95': round(100 * pctile(xs, 95), 3),
                   'share_of_sum_from_top5pct': round(100 * sum(top5) / tot, 1) if tot else None,
                   'pct_over_20': round(100 * sum(1 for x in xs if x > 0.20) / len(xs), 2)}

    out = {'meta': {'stocks': used, 'stock_days': len(base['next1']),
                    'last_bar': last_bar, 'history_dir': hist},
           'baseline': {k: summ(v) for k, v in base.items()},
           'gap_up_next1': cell_table(up), 'gap_up_fwd5': cell_table(up5),
           'gap_down_next1': cell_table(dn), 'gap_down_fwd5': cell_table(dn5),
           'cross_next1': {f'{k[0]} | {k[1]}': summ(v) for k, v in sorted(cross.items()) if summ(v)},
           'cross_fwd5': {f'{k[0]} | {k[1]}': summ(v) for k, v in sorted(cross5.items()) if summ(v)},
           'fat_tail': dsum,
           'latest_session': {'date': last_bar, **today,
                              'faded_pct': round(100 * today['faded'] / max(1, today['gapup']), 1),
                              'filled_pct': round(100 * today['filled'] / max(1, today['gapup']), 1),
                              'top_gap_ups': sorted(latest.values(), key=lambda r: -r['gap'])}}
    print(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    import io
    main()
