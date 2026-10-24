import numpy as np, sys
import os; sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','scripts'))
from scipy.signal import fftconvolve, butter, sosfiltfilt
FS=48000
def xcorr_bands(a,b,maxlag_ms=1.0):
    """max |normalised cross-correlation| within +-maxlag per octave band (what the ear reads as image width)"""
    res=[]
    L=int(FS*maxlag_ms/1000)
    for lo,hi in ((250,500),(500,1000),(1000,2000),(2000,4000),(4000,8000)):
        sos=butter(4,[lo,hi],btype='band',fs=FS,output='sos')
        x=sosfiltfilt(sos,a); y=sosfiltfilt(sos,b)
        n=np.sqrt((x**2).sum()*(y**2).sum())
        c=[ (x[L+k:len(x)-L+k]*y[L:len(y)-L]).sum()/n for k in range(-L,L+1)]
        res.append(np.max(np.abs(c)))
    return res
def evaluate(irs,label):
    rng=np.random.default_rng(5); x=rng.standard_normal(FS*20)
    out={n:fftconvolve(x,h)[:len(x)] for n,h in irs.items()}
    print(label)
    for a,b in (("sl","sr"),("tl","tr"),("sl","tl")):
        print(f"  {a}/{b} max|xcorr| +-1ms  "+"  ".join(f"{v:.2f}" for v in xcorr_bands(out[a],out[b])), "(bands 250-500 ... 4-8k)")
    print("  source vs sl  "+"  ".join(f"{v:.2f}" for v in xcorr_bands(x,out['sl'])))
if __name__=="__main__":
    import upmix as U
    evaluate({n:U.decorrelator(s,tau_ms=t) for n,(s,t) in U.IR_SEEDS.items()},"CURRENT decorrelators")
