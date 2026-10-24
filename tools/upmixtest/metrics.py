import numpy as np, harness as H
from scipy.signal import butter, sosfilt
FS=48000
NAMES=["FL","FR","TL","TR","FC","LFE","SL","SR"]
def pink(n,seed):
    rng=np.random.default_rng(seed); w=rng.standard_normal(n); W=np.fft.rfft(w); f=np.fft.rfftfreq(n,1/FS); f[0]=f[1]
    p=np.fft.irfft(W/np.sqrt(f),n); p/=np.sqrt(np.mean(p**2)); return p*0.1   # -20 dBFS rms
def band(x,lo=200,hi=6000):
    sos=butter(4,[lo,hi],'band',fs=FS,output='sos'); return sosfilt(sos,x,axis=0)
def rms_db(x): return 20*np.log10(np.sqrt(np.mean(x**2))+1e-12)
def table(y,ref=None,label=""):
    yb=band(y[FS:FS*9])
    lv=[rms_db(yb[:,c]) for c in range(8)]
    print(label.ljust(34)+" ".join(f"{NAMES[c]}:{lv[c]:6.1f}" for c in range(8)))
    return yb,lv
def corr(yb,a,b):
    return float(np.corrcoef(yb[:,a],yb[:,b])[0,1])
