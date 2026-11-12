import json, math, random, sys, time
sys.path.insert(0, ".")
from spl.estructuras import *
rnd = random.Random(2026)
out = {"merge": [], "dot": [], "bin": [], "mat": [], "matvec": []}
for n in (8, 16, 32, 64, 128, 256):
    v = [rnd.randint(-1000, 1000) for _ in range(n)]
    t = time.time(); r, e = ejecutar_merge_sort(v, max_ciclos=50_000_000)
    assert r == sorted(v)
    out["merge"].append(dict(n=n, ins=e.cpu.instrucciones, cic=e.cpu.ciclos, t=time.time()-t, ok=r == sorted(v)))
for n in (8, 32, 128, 256):
    a = [rnd.randint(-99, 99) for _ in range(n)]; b = [rnd.randint(-99, 99) for _ in range(n)]
    r, e = ejecutar_producto_punto(a, b, max_ciclos=50_000_000)
    out["dot"].append(dict(n=n, ins=e.cpu.instrucciones, cic=e.cpu.ciclos, ok=r == sum(x*y for x, y in zip(a, b))))
for n in (8, 32, 128, 256):
    v = sorted(rnd.sample(range(-5000, 5000), n)); q = [v[0], v[-1], v[n//2], 99999]
    r, e = ejecutar_busqueda_binaria(v, q, max_ciclos=50_000_000)
    out["bin"].append(dict(n=n, ins=e.cpu.instrucciones, cic=e.cpu.ciclos, ok=r == [v.index(x) if x in v else -1 for x in q]))
for n in (2, 4, 8, 12, 16):
    A = [[rnd.randint(-9, 9) for _ in range(n)] for _ in range(n)]; B = [[rnd.randint(-9, 9) for _ in range(n)] for _ in range(n)]
    C, _, e = ejecutar_multiplicacion_matrices(A, B, max_ciclos=200_000_000)
    out["mat"].append(dict(n=n, ins=e.cpu.instrucciones, cic=e.cpu.ciclos, ok=C == [[sum(A[i][k]*B[k][j] for k in range(n)) for j in range(n)] for i in range(n)]))
for n in (4, 8, 16):
    A = [[rnd.randint(-9, 9) for _ in range(n)] for _ in range(n)]; x = [rnd.randint(-9, 9) for _ in range(n)]
    y, e = ejecutar_matriz_por_vector(A, x, max_ciclos=50_000_000)
    out["matvec"].append(dict(n=n, ins=e.cpu.instrucciones, cic=e.cpu.ciclos, ok=y == [sum(A[i][k]*x[k] for k in range(n)) for i in range(n)]))
r, e = ejecutar_merge_sort(); out["demo_merge"] = dict(r=r, mmio=e.salida_mmio)
out["demo_dot"] = ejecutar_producto_punto()[0]
out["demo_bin"] = ejecutar_busqueda_binaria()[0]
c, y, _ = ejecutar_multiplicacion_matrices(); out["demo_mat"] = dict(C=c, y=y)
json.dump(out, open(sys.argv[1], "w"), indent=1)
for k, v in out.items(): print(k, v)
