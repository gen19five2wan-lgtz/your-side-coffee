"""Rigid-rod model of a person lying across two opposite-moving handrails (top view).
Rails run along y at x = -d/2 (moves -y) and x = +d/2 (moves +y).
Rod: length L, mass m, uniform (I = mL^2/12). theta = angle from x-axis.
"""
import numpy as np

g = 9.8
d = 0.50      # handrail gap [m]
v = 0.67      # handrail speed [m/s]  (= 40 m/min)
L = 1.70      # body length [m]
mu = 0.6      # rubber handrail vs clothes
m = 60.0
I = m * L**2 / 12
EPS = 1e-3    # friction regularization [m/s]


def deriv(s):
    xc, yc, th, vx, vy, w = s
    c, sn = np.cos(th), np.sin(th)
    e = np.array([c, sn]); ep = np.array([-sn, c])
    rails = [(-d/2, -v), (d/2, v)]
    ss = [(xr - xc) / c for xr, _ in rails]
    s1, s2 = ss
    N = [m*g*s2/(s2-s1), m*g*(-s1)/(s2-s1)]
    F = np.zeros(2); tau = 0.0; forces = []
    for (xr, vr), si, Ni in zip(rails, ss, N):
        vp = np.array([vx, vy]) + w*si*ep
        u = vp - np.array([0, vr])
        Fi = -mu*Ni*u/np.sqrt(u@u + EPS**2)
        F += Fi; tau += si*(ep@Fi); forces.append(Fi)
    return np.array([vx, vy, w, F[0]/m, F[1]/m, tau/I]), ss, forces


def run(dt=1e-4, tmax=5.0):
    s = np.zeros(6)
    out = []
    t = 0.0
    while t < tmax:
        ds, ss, f = deriv(s)
        out.append((t, *s, ss[0], ss[1], *f[0], *f[1]))
        if max(abs(ss[0]), abs(ss[1])) > L/2:
            break
        # RK4
        k1 = ds
        k2 = deriv(s+dt/2*k1)[0]
        k3 = deriv(s+dt/2*k2)[0]
        k4 = deriv(s+dt*k3)[0]
        s = s + dt/6*(k1+2*k2+2*k3+k4)
        t += dt
    return np.array(out)


if __name__ == "__main__":
    a = run()
    t, th, w = a[-1, 0], a[-1, 3], a[-1, 6]
    print(f"fall at t={t:.3f}s theta={np.degrees(th):.1f}deg omega={w:.2f}rad/s "
          f"({w/2/np.pi:.2f} rev/s) center drift=({a[-1,1]*100:.2f},{a[-1,2]*100:.2f})cm")
    np.save("traj.npy", a)
