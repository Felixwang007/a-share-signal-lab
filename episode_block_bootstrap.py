#!/usr/bin/env python3
"""v4: clustering / block-bootstrap test of the liquidity floor.
Resamples MONTHS (not samples) to respect episode clustering."""
import json, os, glob, statistics as st, collections, random

OUT = r'C:\Users\Administrator\stock_tools\history_ext'
RES = r'C:\Users\Administrator\stock_tools\bootstrap_1026.json'

files=sorted(glob.glob(os.path.join(OUT,'*.json')))
data={}
for fp in files:
    try: df=json.load(open(fp))
    except Exception: continue
    if not isinstance(df,list) or len(df)<60: continue
    data[os.path.basename(fp)[:-5]]=df
market_last=max(d[-1]['date'] for d in data.values())
live={c:d for c,d in data.items() if d[-1]['date']==market_last}

rows=[]
for c,df in live.items():
    for i in range(20,len(df)-5):
        dt=df[i]['date']
        if dt<'2024-01-01': continue
        win=df[i-19:i+1]
        try:
            closes=[float(x['close']) for x in win]; vols=[float(x['volume']) for x in win]
            highs=[float(x['high']) for x in win]
            close=closes[-1]; prev=float(df[i-1]['close'])
            hi=float(win[-1]['high']); lo=float(win[-1]['low'])
            if close<=0 or prev<=0 or hi<=lo: continue
        except Exception: continue
        chg=(close-prev)/prev*100
        ma5=st.mean(closes[-5:]); ma20=st.mean(closes)
        v5=st.mean(vols[-6:-1]); vr=vols[-1]/v5 if v5>0 else 1.0
        c20=(close/closes[0]-1)*100
        if not (ma5<ma20 and c20<=-15 and chg>2.0 and vr>=1.2): continue
        prev_hi20=max(highs[:-1])
        if close>prev_hi20 and vr>=1.5: continue          # breakout takes precedence
        hi20,lo20=max(closes),min(closes)
        pos=(close-lo20)/(hi20-lo20) if hi20>lo20 else 0.5
        if pos>=0.70 and chg<=-3.0 and vr>=1.3: continue  # high_vol_drop precedence
        amt20=st.mean([v*100*float(df[i-19+k]['close']) for k,v in enumerate(vols)])
        fwd=(float(df[i+5]['close'])/close-1)*100
        rows.append(dict(ym=dt[:7], fwd=fwd, amt=amt20, px=close))

print('oversold samples:', len(rows))
bym=collections.defaultdict(list)
for r in rows: bym[r['ym']].append(r)

# concentration
counts=sorted(((len(v),k) for k,v in bym.items()), reverse=True)
tot=len(rows)
print('\nTop months by signal count:')
acc=0
for n,m in counts[:10]:
    acc+=n; print('  %s n=%-5d cum=%.1f%%' % (m,n,acc/tot*100))
big=[m for n,m in counts if n>=100]
print('\nmonths total=%d  months with n>=100: %d (share of samples %.1f%%)' % (
    len(bym), len(big), sum(len(bym[m]) for m in big)/tot*100))

def mean(xs): return st.mean(xs) if xs else None

# block bootstrap over months: diff in mean between floor and all
random.seed(20261026)
months=list(bym)
B=10000
diffs=[]; base_ns=[]
for _ in range(B):
    samp=[random.choice(months) for _ in months]
    allv=[]; fl=[]
    for m in samp:
        for r in bym[m]:
            allv.append(r['fwd'])
            if r['amt']>=5e7 and r['px']>=3: fl.append(r['fwd'])
    if fl and allv: diffs.append(st.mean(fl)-st.mean(allv))
diffs.sort()
lo,hi=diffs[int(0.025*len(diffs))], diffs[int(0.975*len(diffs))]
point=(st.mean([r['fwd'] for r in rows if r['amt']>=5e7 and r['px']>=3])
       - st.mean([r['fwd'] for r in rows]))
print('\nfloor(amt>=50M & px>=3) vs all: point diff %+.3f pp | 95%% month-block bootstrap CI [%+.3f, %+.3f]' % (point, lo, hi))
print('share of bootstrap draws where floor is worse: %.1f%%' % (sum(1 for d in diffs if d<0)/len(diffs)*100))

# naive iid bootstrap for contrast
iid=[]
allv=[r['fwd'] for r in rows]; fl=[r['fwd'] for r in rows if r['amt']>=5e7 and r['px']>=3]
for _ in range(B):
    a=[random.choice(allv) for _ in allv]; b=[random.choice(fl) for _ in fl]
    iid.append(st.mean(b)-st.mean(a))
iid.sort()
print('naive iid bootstrap CI: [%+.3f, %+.3f]  (wrong: ignores clustering)' % (iid[int(0.025*B)], iid[int(0.975*B)]))

# per-month diff table (2026 only for the article)
out=dict(oversold=len(rows), months=len(bym), months_n100=len(big),
         top_months=[(m,n,round(n/tot*100,1)) for n,m in counts[:10]],
         floor_point=round(point,3), boot_ci=[round(lo,3),round(hi,3)],
         iid_ci=[round(iid[int(0.025*B)],3), round(iid[int(0.975*B)],3)],
         pct_draws_floor_worse=round(sum(1 for d in diffs if d<0)/len(diffs)*100,1),
         monthly={m:dict(n=len(v), mean=round(mean([x['fwd'] for x in v]),3)) for m,v in sorted(bym.items())})
json.dump(out, open(RES,'w',encoding='utf-8'), ensure_ascii=False, indent=1)

# effective independent episodes = count of months with n>=100
print('\n2026 months detail:')
for m in sorted(bym):
    if m.startswith('2026'):
        v=bym[m]; f=[x['fwd'] for x in v if x['amt']>=5e7 and x['px']>=3]
        print('  %s n=%-4d all=%+.2f floor_n=%-4d floor=%s' % (m,len(v),mean([x['fwd'] for x in v]),len(f), ('%+.2f'%mean(f)) if f else 'NA'))
