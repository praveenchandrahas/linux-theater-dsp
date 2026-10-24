import numpy as np, harness as H, metrics as M
n=48000*10
a=M.pink(n,1); b=M.pink(n,2); m=M.pink(n,3)
ref=M.rms_db(M.band(a[48000:48000*9]))
print(f"input band level {ref:.1f} dB (reference 0)")
def show(y,label):
    yb=M.band(y[48000:48000*9]); lv=[M.rms_db(yb[:,c])-ref for c in range(8)]
    print(label.ljust(24)+" ".join(f"{M.NAMES[c]}:{lv[c]:6.1f}" for c in range(8)))
    return yb
for fl in ("voice","balanced","wide"):
    print("== stereo",fl)
    show(H.run(np.c_[m,m],"stereo",fl,full=False,tag="a"),"mono (voice)")
    yb=show(H.run(np.c_[a,b],"stereo",fl,full=False,tag="a"),"uncorrelated pair")
    print("   corr SL/SR %.2f TL/TR %.2f FL/FR %.2f SL/FL %.2f TL/FL %.2f"%(M.corr(yb,6,7),M.corr(yb,2,3),M.corr(yb,0,1),M.corr(yb,6,0),M.corr(yb,2,0)))
    show(H.run(np.c_[a,0*a],"stereo",fl,full=False,tag="a"),"hard left")
for fl in ("subtle","balanced","wide"):
    print("== bed",fl)
    x=np.zeros((n,8)); x[:,0]=a;x[:,1]=b;x[:,4]=m;x[:,6]=M.pink(n,4);x[:,7]=M.pink(n,5)
    yb=show(H.run(x,"bed",fl,full=False,tag="b"),"full 5.1 noise")
    x=np.zeros((n,8)); x[:,4]=m
    show(H.run(x,"bed",fl,full=False,tag="b"),"dialogue only (FC)")
