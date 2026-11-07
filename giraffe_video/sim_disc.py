"""実現例: 丸い台(円盤)を2本の逆向きに動く手すりにのせたとき(上から見た図)。
sim.py と同じ d, v, μ, m。円盤の中心は対称性で動かない(x/y の合力は0)。回転だけを積分する。
円盤は手すりの線に沿った弦(長さ 2*sqrt(R^2-(d/2)^2))で接し、荷重はその弦に一様と仮定。
"""
import numpy as np
from sim import d, v, mu, m, g, EPS
R = 0.60                      # 丸い台の半径 [m](直径1.2m)
I = 0.5*m*R**2
c = np.sqrt(R**2 - (d/2)**2)
NS = 81
ds = 2*c/NS
ss = (np.arange(NS) + 0.5)*ds - c

def torque(w):
    dens = (m*g/2)/(2*c)
    tau = 0.0
    for xr, vr in ((-d/2, -v), (d/2, v)):
        ux = -w*ss; uy = w*xr - vr
        nrm = np.sqrt(ux**2 + uy**2 + EPS**2)
        Fx = -mu*dens*ds*ux/nrm; Fy = -mu*dens*ds*uy/nrm
        tau += np.sum(xr*Fy - ss*Fx)
    return tau

def run(dt=1e-3, tmax=20.0):
    n = int(tmax/dt) + 1
    th = np.zeros(n); w = 0.0
    for i in range(1, n):
        k1 = torque(w)/I
        k2 = torque(w + dt/2*k1)/I
        k3 = torque(w + dt/2*k2)/I
        k4 = torque(w + dt*k3)/I
        wn = w + dt/6*(k1 + 2*k2 + 2*k3 + k4)
        th[i] = th[i-1] + dt*(w + wn)/2
        w = wn
    return th, w

if __name__ == "__main__":
    th, w = run()
    np.save("disc_traj.npy", th)
    import json; json.dump(np.round(th, 6).tolist(), open("web3d/disc_traj.json", "w"))
    t = np.arange(len(th))*1e-3
    for T in (1, 2, 4, 8, 12, 20):
        i = int(T/1e-3)
        print(f"t={T:5.1f}s  angle={np.degrees(th[i]):9.1f}deg  ({th[i]/2/np.pi:6.2f} rev)  omega={(th[i]-th[i-1])/1e-3:.3f} rad/s")
    print("final omega", round(w, 3), "rad/s;  rolling-without-slip limit 2v/d =", round(2*v/d, 3))
