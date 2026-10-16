import sys,time,json,warnings,statistics,threading
import requests
src=sys.argv[1]; steps=[int(x) for x in sys.argv[2].split(',')]; dur=float(sys.argv[3])
import yaml; syms=yaml.safe_load(open('/app/config/ingestion.yaml'))['symbols']
http=[]
orig=requests.Session.send
def send(self,req,**kw):
    t=time.monotonic(); r=orig(self,req,**kw)
    h={k:v for k,v in r.headers.items() if 'rate' in k.lower() or k.lower() in('retry-after','x-ratelimit-remaining')}
    http.append((r.status_code,int((time.monotonic()-t)*1000),h,req.url.split('?')[0][:80]));return r
requests.Session.send=send
from vnstock import Market
m=Market()
def tag(): return time.strftime('[DBG-%Y%m%d-%H%M-INGEST-RATEPROBE]')
base=None; res=[]
for rpm in steps:
    gap=60.0/rpm; n=max(3,int(dur/gap)); lat=[]; errs=[]; codes={}; hdr={}
    http.clear(); t0=time.monotonic()
    for i in range(n):
        nxt=t0+i*gap; d=nxt-time.monotonic()
        if d>0: time.sleep(d)
        s=time.monotonic()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore'); f=m.price_board(list(syms),source=src.lower())
            if f is None or len(f)==0: raise ValueError('empty')
        except BaseException as e:
            errs.append(f'{type(e).__name__}:{str(e)[:120]}')
        lat.append(int((time.monotonic()-s)*1000))
    for c,_,h,u in http: codes[c]=codes.get(c,0)+1; hdr.update(h)
    lat.sort(); p50=lat[len(lat)//2]; p95=lat[min(len(lat)-1,int(len(lat)*.95))]
    bad=[c for c in codes if c in(429,403) or c>=500]
    r=dict(src=src,rpm=rpm,calls=n,http_calls=len(http),codes=codes,p50=p50,p95=p95,errs=errs[:3],nerr=len(errs),hdr=hdr,urls=sorted({u for *_,u in http}))
    print(tag(),json.dumps(r),flush=True); res.append(r)
    if base is None: base=p50
    if errs or bad or p95>max(3*base,base+1500):
        print(tag(),src,'STOP at',rpm,flush=True); break
print(tag(),'DONE',src,flush=True)
