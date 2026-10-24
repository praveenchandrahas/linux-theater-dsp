import sys, os, subprocess, wave, importlib.util
import numpy as np
CD=os.environ.get("CAMILLADSP","camilladsp")
ROOT=os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..')
sys.path.insert(0,os.path.join(ROOT,'scripts'))
spec=importlib.util.spec_from_file_location('seteq',os.path.join(ROOT,'scripts','set-eq.py')); sys.argv=['x']
S=importlib.util.module_from_spec(spec); spec.loader.exec_module(S)
FS=48000
def head(inp,out):
    return f"""devices:
  samplerate: 48000
  chunksize: 1024
  capture:
    type: WavFile
    filename: "{inp}"
  playback:
    type: File
    channels: 8
    format: F32_LE
    filename: "{out}"
"""
def write_wav(path,x):  # x: (n,8) float in [-1,1], 16-bit would limit; use 24 bit? use float32 wav via ffmpeg? use PCM32
    x=np.clip(x,-1,1)
    pcm=np.round(x*2147483647).astype('<i4')
    w=wave.open(path,'wb'); w.setnchannels(x.shape[1]); w.setsampwidth(4); w.setframerate(FS); w.writeframes(pcm.tobytes()); w.close()
def run(x, kind=None, flavour=None, full=True, tag="t", opts=None):
    """x: (n,2) or (n,8). Returns (n,8) processed by the full standing profile (+upmix)."""
    if x.shape[1]==2:
        y=np.zeros((x.shape[0],8)); y[:,0]=x[:,0]; y[:,1]=x[:,1]; x=y
    n=x.shape[0]
    x=np.vstack([x,np.zeros((FS//2,8))])
    inp=f"{tag}_in.wav"; out=f"{tag}_out.raw"
    write_wav(inp,x)
    chosen=[(nm,f,g,q) for nm,f,g,q in S.FILTER_SETS['drone2'] if f<=300] if full else []
    heights={"hp":140,"lfe_gain":0.0,"tone":True} if full else None
    up=(kind,flavour,"ir") if kind else None
    cfg=S.build_config(chosen,'all' if full else None,(),heights,upmix=up,head=head(inp,out))
    open(f"{tag}.yml","w").write(cfg)
    r=subprocess.run([CD,f"{tag}.yml"],capture_output=True,text=True)
    if r.returncode!=0 or not os.path.exists(out):
        print(r.stdout[-800:],r.stderr[-800:]); raise SystemExit("camilladsp failed")
    y=np.fromfile(out,dtype='<f4').reshape(-1,8)
    return y[:n+FS//2]
