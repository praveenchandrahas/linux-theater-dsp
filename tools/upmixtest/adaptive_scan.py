import numpy as np, io, contextlib, adaptive_eval as E, adaptive as A, metrics as M
FS=48000
rows=[]
def one(label, inst, pan, **kw):
    buf=io.StringIO()
    with contextlib.redirect_stdout(buf): E.report(label, inst, pan, **kw)
    line=buf.getvalue().strip().split("| adaptive:")[1]
    return line.strip()
sp_hard, sp_ctr, dn_hard = E.sparse(1), E.sparse(7), E.dense(1)
print("q = exponent on directness (lower = subtract more of the direct part); alpha = time smoothing")
for q in (1.0, 0.6, 0.4):
    for alpha in (0.85, 0.93):
        print(f"q={q} alpha={alpha}")
        print("   harmonic hard-left :", one("", sp_hard, 0.0, q=q, alpha=alpha))
        print("   harmonic centre    :", one("", sp_ctr, 1.0, q=q, alpha=alpha))
        print("   dense hard-left    :", one("", dn_hard, 0.0, q=q, alpha=alpha))
