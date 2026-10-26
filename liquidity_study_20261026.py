#!/usr/bin/env python3
"""v2 clean study: live universe only (last bar == market last date), samples >= 2024-01-01
Tests: liquidity buckets, liquidity floors, price floor, cost netting, per-year stability, live scan
"""
import json, os, glob, statistics as st, collections

OUT = r'C:\Users\Administrator\stock_tools\history_ext'
RES = r'C:\Users\Administrator\stock_tools\clean_study_1026.json'
START = '2024-01-01'

def classify(df, i, need_fwd=True):
    if i < 20: return None
    if need_fwd and i + 5 >= len(df): return None
    win = df[i-19:i+1]
    try:
        closes=[float(x['close']) for x in win]; highs=[float(x['high']) for x in win]
        vols=[float(x['volume']) for x in win]
        cur=win[-1]; close=float(cur['close']); prev_close=float(df[i-1]['close'])
        hi=float(cur['high']); lo=float(cur['low']); vol=float(cur['volume'])
    except Exception:
        return None
    if close<=0 or prev_close<=0 or hi<=lo: return None
    chg=(close-prev_close)/prev_close*100
    ma5=st.mean(closes[-5:]); ma10=st.mean(closes[-10:]); ma20=st.mean(closes)
    v5=st.mean(vols[-6:-1]) if len(vols)>=6 else vol
    vr=vol/v5 if v5>0 else 1.0
    hi20,lo20=max(closes),min(closes)
    pos=(close-lo20)/(hi20-lo20) if hi20>lo20 else 0.5
    prev_hi20=max(highs[:-1]); c20=(close/closes[0]-1)*100
    fwd5=(float(df[i+5]['close'])/close-1)*100 if need_fwd else None
    amt20=st.mean([v*100*float(df[i-19+k]['close']) for k,v in enumerate(vols)])
    sig=None
    if close>prev_hi20 and vr>=1.5: sig='breakout'
    elif pos>=0.70 and chg<=-3.0 and vr>=1.3: sig='high_vol_drop'
    elif ma5<ma20 and c20<=-15 and chg>2.0 and vr>=1.2: sig='oversold_bounce'
    elif ma5>ma20 and chg<0 and vr<=0.85: sig='quiet_pullback'
    elif ma5>ma10>ma20 and close>ma20: sig='uptrend'
    elif (hi20-lo20)/lo20*100<8 and abs(chg)<1.5: sig='flat'
    if sig is None: return None
    return dict(sig=sig, fwd5=fwd5, amt20=amt20, close=close, chg=chg, c20=c20, vr=vr,
                date=df[i]['date'], code=df[i].get('code',''))

def bucket(a):
    if a<2e7: return '<20M'
    if a<5e7: return '20-50M'
    if a<1e8: return '50-100M'
    if a<3e8: return '100-300M'
    if a<1e9: return '300M-1B'
    return '>=1B'
ORDER=['<20M','20-50M','50-100M','100-300M','300M-1B','>=1B']

def s(xs):
    if not xs: return None
    n=len(xs)
    return dict(n=n, mean=round(st.mean(xs),3), median=round(st.median(xs),3),
                win=round(sum(1 for x in xs if x>0)/n*100,1))

files=sorted(glob.glob(os.path.join(OUT,'*.json')))
data={}
for fp in files:
    try: df=json.load(open(fp))
    except Exception: continue
    if not isinstance(df,list) or len(df)<60: continue
    data[os.path.basename(fp)[:-5]]=df
market_last=max(d[-1]['date'] for d in data.values())
live={c:d for c,d in data.items() if d[-1]['date']==market_last}

samples=collections.defaultdict(list)
for c,df in live.items():
    for i in range(20, len(df)-5):
        if df[i]['date'] < START: continue
        r=classify(df,i)
        if r: samples[r['sig']].append(r)

osb=samples['oversold_bounce']
buckets=collections.defaultdict(list)
for r in osb: buckets[bucket(r['amt20'])].append(r['fwd5'])

out=dict(meta=dict(files=len(data), live=len(live), market_last=market_last,
                   start=START, total_samples=sum(len(v) for v in samples.values()),
                   oversold_n=len(osb)),
         by_signal={k:s([x['fwd5'] for x in v]) for k,v in samples.items()},
         oversold_all=s([x['fwd5'] for x in osb]),
         buckets={b:s(buckets[b]) for b in ORDER if buckets[b]})

# floors
floors={}
for th,lab in [(2e7,'amt>=20M'),(5e7,'amt>=50M'),(1e8,'amt>=100M')]:
    floors[lab]=s([x['fwd5'] for x in osb if x['amt20']>=th])
for p,lab in [(2,'px>=2'),(3,'px>=3'),(5,'px>=5')]:
    floors[lab]=s([x['fwd5'] for x in osb if x['close']>=p])
floors['amt>=50M & px>=3']=s([x['fwd5'] for x in osb if x['amt20']>=5e7 and x['close']>=3])
floors['amt>=50M & px>=3 & c20>=-40']=s([x['fwd5'] for x in osb if x['amt20']>=5e7 and x['close']>=3 and x['c20']>=-40])
out['floors']=floors

# per-year x bucket
yb=collections.defaultdict(lambda: collections.defaultdict(list))
for r in osb: yb[r['date'][:4]][bucket(r['amt20'])].append(r['fwd5'])
out['year_bucket']={y:{b:s(yb[y][b]) for b in ORDER if yb[y][b]} for y in sorted(yb)}

# cost: A-share round trip ~0.11% fees + slippage 0.1% = 0.21% ; net edge per bucket
net={}
for b in ORDER:
    v=out['buckets'].get(b)
    if v: net[b]=round(v['mean']-0.21,3)
out['net_after_cost']=net

# live scan today
live_hits=collections.defaultdict(list)
for c,df in live.items():
    r=classify(df, len(df)-1, need_fwd=False)
    if r: live_hits[r['sig']].append(r)
out['live_counts']={k:len(v) for k,v in live_hits.items()}
cand=[dict(code=r['code'], close=round(r['close'],2), chg=round(r['chg'],2),
           c20=round(r['c20'],1), vr=round(r['vr'],2), amt_m=round(r['amt20']/1e6,1))
      for r in live_hits['oversold_bounce']]
strict=[c for c in cand if c['amt_m']>=50 and c['close']>=3 and c['c20']>=-40]
out['live_oversold_total']=len(cand)
out['live_oversold_strict']=sorted(strict, key=lambda x:-x['amt_m'])

json.dump(out, open(RES,'w',encoding='utf-8'), ensure_ascii=False, indent=1)

print('META', out['meta'])
print('\nSIGNALS (2024-01-01+, live universe):')
for k,v in sorted(out['by_signal'].items(), key=lambda kv:-kv[1]['mean']):
    print(' %-16s n=%-7d mean=%+.3f median=%+.3f win=%.1f%%' % (k,v['n'],v['mean'],v['median'],v['win']))
print('\nOVERSOLD by liquidity:')
for b in ORDER:
    v=out['buckets'].get(b)
    if v: print(' %-9s n=%-5d mean=%+.3f median=%+.3f win=%.1f%% net@0.21%%=%+.3f' % (b,v['n'],v['mean'],v['median'],v['win'],net[b]))
print('\nFLOORS:')
for k,v in out['floors'].items():
    if v: print(' %-26s n=%-5d mean=%+.3f median=%+.3f win=%.1f%%  kept=%.1f%%' % (k,v['n'],v['mean'],v['median'],v['win'],v['n']/len(osb)*100))
print('\nPER-YEAR x bucket:')
for y in sorted(yb):
    print(' ',y, {b:(out['year_bucket'][y][b]['mean'], out['year_bucket'][y][b]['n']) for b in ORDER if b in out['year_bucket'][y]})
print('\nLIVE today', market_last, out['live_counts'])
print('oversold total', out['live_oversold_total'], 'strict', len(out['live_oversold_strict']))
for c in out['live_oversold_strict']: print('  ', c)
