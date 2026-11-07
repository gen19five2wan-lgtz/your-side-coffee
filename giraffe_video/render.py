import numpy as np, subprocess, wave, math
from PIL import Image, ImageDraw, ImageFont
from sim import d, v, L, mu

W, H, SS, FPS = 720, 1280, 2, 30
CW, CH = W*SS, H*SS
BLACK = "FONT_BLACK"
FB = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
FM = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
_fc = {}
def font(size, black=True):
    k = (size, black)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FB if black else FM, size*SS, index=0)
    return _fc[k]

YEL = (255, 212, 0); RED = (230, 50, 40); BLU = (40, 110, 230)
INK = (20, 20, 20); PAPER = (245, 244, 238); GRAY = (150, 150, 150)

traj = np.load("traj.npy")
DT = 1e-4
T_FALL = traj[-1, 0]
TH_FALL = traj[-1, 3]

def state(ts):
    i = min(int(round(ts/DT)), len(traj)-1)
    return traj[i]

def ease(x): x = min(max(x, 0), 1); return x*x*(3-2*x)

def text(dr, xy, s, size, fill=INK, black=True, anchor="mm", alpha=1.0, stroke=0, stroke_fill=None):
    x, y = xy
    if alpha < 1:
        fill = tuple(int(c*alpha + b*(1-alpha)) for c, b in zip(fill, dr._bg))
    dr.text((x*SS, y*SS), s, font=font(size, black), fill=fill, anchor=anchor,
            stroke_width=stroke*SS, stroke_fill=stroke_fill)

def canvas(bg):
    im = Image.new("RGB", (CW, CH), bg)
    dr = ImageDraw.Draw(im); dr._bg = bg
    return im, dr

# ---------- top-view stage ----------
PPM = 330            # pixels per metre (output px)
CX, CY = W/2, 600    # world origin on screen
def w2s(x, y): return ((CX + x*PPM)*SS, (CY - y*PPM)*SS)

def draw_stage(dr, ts, ystretch=1.0):
    """walkways + handrails; ts = sim time used for belt motion"""
    top, bot = 120, 1080
    # walkway floors
    for side, sgn in ((-1, -1), (1, 1)):
        x0 = CX + side*(d/2*PPM + 14); x1 = CX + side*W
        xa, xb = sorted((x0, x1))
        dr.rectangle([xa*SS, top*SS, xb*SS, bot*SS], fill=(205, 205, 200))
        off = (sgn*v*ts*PPM) % 22
        y = top - 22 + off
        while y < bot:
            dr.line([xa*SS, y*SS, xb*SS, y*SS], fill=(185, 185, 180), width=3*SS)
            y += 22
        # direction arrows
        ax = CX + side*(d/2*PPM + 110)
        for k in range(4):
            yy = top + ((k*240 - sgn*v*ts*PPM) % 960)
            tip = -sgn*26
            dr.polygon([(ax*SS, (yy+tip)*SS), ((ax-18)*SS, (yy-tip*0.2)*SS), ((ax+18)*SS, (yy-tip*0.2)*SS)],
                       fill=(160, 160, 155))
    # gap between rails (fall zone)
    dr.rectangle([(CX - d/2*PPM + 14)*SS, top*SS, (CX + d/2*PPM - 14)*SS, bot*SS], fill=(60, 60, 64))
    # handrails
    for side, sgn in ((-1, -1), (1, 1)):
        xr = CX + side*d/2*PPM
        dr.rectangle([(xr-14)*SS, top*SS, (xr+14)*SS, bot*SS], fill=(25, 25, 25))
        off = (sgn*v*ts*PPM) % 40
        y = top - 40 + off
        while y < bot:
            dr.line([(xr-10)*SS, y*SS, (xr+10)*SS, y*SS], fill=YEL, width=4*SS)
            y += 40

def draw_body(dr, xc, yc, th, color=BLU, alpha_bg=None, scale=1.0, outline=True):
    c, s = math.cos(th), math.sin(th)
    half = L/2*scale
    # body capsule (feet at -end, head at +end)
    hx, hy = xc + c*half, yc + s*half
    fx, fy = xc - c*half, yc - s*half
    nx, ny = xc + c*(half-0.17*scale), yc + s*(half-0.17*scale)
    p1, p2 = w2s(fx, fy), w2s(nx, ny)
    wid = int(0.30*PPM*scale*SS)
    if outline:
        dr.line([p1, p2], fill=INK, width=wid+6*SS)
        for p in (p1, p2):
            r = (wid+6*SS)/2; dr.ellipse([p[0]-r, p[1]-r, p[0]+r, p[1]+r], fill=INK)
    dr.line([p1, p2], fill=color, width=wid)
    for p in (p1, p2):
        r = wid/2; dr.ellipse([p[0]-r, p[1]-r, p[0]+r, p[1]+r], fill=color)
    hp = w2s(hx - c*0.06*scale, hy - s*0.06*scale)
    r = 0.11*PPM*scale*SS
    dr.ellipse([hp[0]-r, hp[1]-r, hp[0]+r, hp[1]+r], fill=(250, 220, 190), outline=INK, width=3*SS)

def arrow(dr, p, vec, color, width=8):
    x0, y0 = p; x1, y1 = x0+vec[0], y0+vec[1]
    ln = math.hypot(vec[0], vec[1])
    if ln < 4: return
    ux, uy = vec[0]/ln, vec[1]/ln
    hl = 26*SS
    bx, by = x1-ux*hl, y1-uy*hl
    dr.line([x0, y0, bx, by], fill=color, width=width*SS)
    dr.polygon([(x1, y1), (bx-uy*16*SS, by+ux*16*SS), (bx+uy*16*SS, by-ux*16*SS)], fill=color)

def sim_view(dr, ts, trails=False, forces=False, center=False, hud=True, slow_label=None):
    fell = ts >= T_FALL
    st = state(min(ts, T_FALL))
    draw_stage(dr, ts)
    if trails:
        k = 0.15
        while k < min(ts, T_FALL):
            s2 = state(k); c, sn = math.cos(s2[3]), math.sin(s2[3])
            dr.line([w2s(s2[1]-c*L/2, s2[2]-sn*L/2), w2s(s2[1]+c*L/2, s2[2]+sn*L/2)],
                    fill=(140, 165, 220), width=5*SS)
            k += 0.15
    if not fell:
        draw_body(dr, st[1], st[2], st[3])
        if forces:
            for si, fx, fy in ((st[7], st[9], st[10]), (st[8], st[11], st[12])):
                px = st[1] + si*math.cos(st[3]); py = st[2] + si*math.sin(st[3])
                p = w2s(px, py)
                sc = 0.9*SS
                arrow(dr, p, (fx*sc, -fy*sc), RED)
                dr.ellipse([p[0]-9*SS, p[1]-9*SS, p[0]+9*SS, p[1]+9*SS], fill=RED)
    else:
        k = ease((ts - T_FALL)/0.35)
        sc = 1 - 0.35*k
        col = tuple(int(a*(1-k) + b*k) for a, b in zip(BLU, (90, 90, 100)))
        draw_body(dr, st[1], st[2], st[3] + 0.15*k, color=col, scale=sc)
    if center:
        p = w2s(st[1], st[2])
        dr.line([p[0]-22*SS, p[1], p[0]+22*SS, p[1]], fill=YEL, width=5*SS)
        dr.line([p[0], p[1]-22*SS, p[0], p[1]+22*SS], fill=YEL, width=5*SS)
    if hud:
        # stopwatch + angle panel
        dr.rectangle([0, 1080*SS, CW, CH], fill=INK)
        tshow = min(ts, T_FALL)
        text(dr, (190, 1150), "経過時間", 30, fill=(200, 200, 200), black=False)
        text(dr, (190, 1215), f"{tshow:4.2f} 秒", 62, fill=(255, 255, 255))
        text(dr, (530, 1150), "回転した角度", 30, fill=(200, 200, 200), black=False)
        text(dr, (530, 1215), f"{math.degrees(st[3]):4.1f}°", 62, fill=YEL)
    if slow_label:
        dr.rectangle([0, 0, CW, 120*SS], fill=INK)
        text(dr, (W/2, 60), slow_label, 44, fill=(255, 255, 255))

# ---------- scenes ----------
scenes = []   # (duration, fn(t_local) -> Image)
def scene(dur):
    def deco(fn): scenes.append((dur, fn)); return fn
    return deco

@scene(5.0)
def title(t):
    im, dr = canvas(INK)
    a1, a2, a3 = ease(t/0.6), ease((t-0.9)/0.6), ease((t-1.9)/0.5)
    text(dr, (W/2, 330), "実験", 40, fill=YEL, alpha=a1)
    text(dr, (W/2, 470), "動く歩道の手すりに", 58, fill=(255, 255, 255), alpha=a1)
    text(dr, (W/2, 560), "またがって寝転んだら", 58, fill=(255, 255, 255), alpha=a2)
    if t > 1.9:
        sz = int(76 + 30*(1-a3))
        text(dr, (W/2, 740), "一生", sz, fill=YEL)
        text(dr, (W/2, 860), "くるくる回るのか？", sz, fill=YEL)
    return im

@scene(7.0)
def setup(t):
    im, dr = canvas(PAPER)
    draw_stage(dr, t)
    a = ease((t-0.8)/0.6)
    if a > 0:
        draw_body(dr, 0, 0, 0)
    # dimension: gap
    y = CY + 210
    x0, x1 = (CX - d/2*PPM)*SS, (CX + d/2*PPM)*SS
    dr.line([x0, y*SS, x1, y*SS], fill=RED, width=5*SS)
    for x in (x0, x1): dr.line([x, (y-18)*SS, x, (y+18)*SS], fill=RED, width=5*SS)
    dr.rectangle([(CX-80)*SS, (y+24)*SS, (CX+80)*SS, (y+80)*SS], fill=(255, 255, 255))
    text(dr, (CX, y+52), "50cm", 40, fill=RED)
    dr.rectangle([0, 0, CW, 120*SS], fill=INK)
    text(dr, (W/2, 60), "実験の条件（上から見た図）", 44, fill=(255, 255, 255))
    dr.rectangle([0, 1080*SS, CW, CH], fill=INK)
    rows = ["手すりの速さ：分速40m（逆向き）", "身長170cm・体はまっすぐな棒として計算", "手すりの摩擦係数：0.6"]
    for i, r in enumerate(rows):
        al = ease((t-1.5-i*0.9)/0.5)
        text(dr, (W/2, 1125+i*58), r, 34, fill=(255, 255, 255), black=False, alpha=al)
    return im

@scene(4.0)
def countdown(t):
    im, dr = canvas(INK)
    if t < 3.0:
        n = 3 - int(t)
        k = t - int(t)
        text(dr, (W/2, H/2), str(n), int(300 - 60*k), fill=(255, 255, 255))
        text(dr, (W/2, 330), "実験開始まで", 44, fill=YEL)
    else:
        text(dr, (W/2, H/2), "スタート", 120, fill=YEL)
    return im

REAL_HOLD = 3.0
@scene(T_FALL + REAL_HOLD)
def realtime(t):
    im, dr = canvas(PAPER)
    sim_view(dr, t, slow_label="実際の速さ")
    if t > T_FALL:
        k = ease((t-T_FALL)/0.25)
        dr.rectangle([(W/2-230)*SS, 520*SS, (W/2+230)*SS, 680*SS], fill=RED)
        text(dr, (W/2, 600), "落下！", int(80+40*(1-k)), fill=(255, 255, 255))
    if t > T_FALL + 1.2:
        text(dr, (W/2, 940), "一瞬で落ちた…", 52, fill=INK, stroke=5, stroke_fill=(255, 255, 255))
    return im

@scene(2.5)
def slowcard(t):
    im, dr = canvas(INK)
    text(dr, (W/2, 560), "スローで", 90, fill=(255, 255, 255), alpha=ease(t/0.4))
    text(dr, (W/2, 700), "見てみよう", 90, fill=(255, 255, 255), alpha=ease((t-0.4)/0.4))
    text(dr, (W/2, 850), "（8分の1の速さ）", 40, fill=YEL, alpha=ease((t-0.8)/0.4))
    return im

SLOW = 8.0
@scene(T_FALL*SLOW + 4.0)
def slowmo(t):
    im, dr = canvas(PAPER)
    ts = t/SLOW if t < T_FALL*SLOW else T_FALL + (t - T_FALL*SLOW)
    sim_view(dr, ts, trails=True, forces=True, center=True, slow_label="スロー 1/8倍速")
    cap = None
    if 0.5 < t < 4.0: cap = "赤い矢印＝手すりが体を引っぱる力"
    elif 4.0 < t < 8.0: cap = "左右で逆向き → 体が回り出す"
    elif 8.0 < t < T_FALL*SLOW: cap = "黄色の十字＝体の中心は動かない"
    elif t > T_FALL*SLOW + 0.3: cap = "約73°回ったところで落下"
    if cap:
        dr.rectangle([0, 128*SS, CW, 200*SS], fill=(255, 255, 255))
        text(dr, (W/2, 164), cap, 36, fill=INK)
    return im

@scene(7.0)
def why(t):
    im, dr = canvas(PAPER)
    dr.rectangle([0, 0, CW, 120*SS], fill=INK)
    text(dr, (W/2, 60), "なぜ一生は回れないのか", 46, fill=(255, 255, 255))
    # rails
    top, bot = 260, 1000
    for side in (-1, 1):
        xr = CX + side*d/2*PPM
        dr.rectangle([(xr-12)*SS, top*SS, (xr+12)*SS, bot*SS], fill=(25, 25, 25))
    cy0 = 630
    items = [(0, "50cm", BLU), (45, "71cm", (110, 80, 200)), (72.9, "170cm", RED)]
    for i, (deg, lab, col) in enumerate(items):
        a = ease((t - 0.4 - i*1.4)/0.5)
        if a <= 0: continue
        th = math.radians(deg)
        need = d/math.cos(th)/2
        x0, y0 = CX - math.cos(th)*need*PPM, cy0 + math.sin(th)*need*PPM
        x1, y1 = CX + math.cos(th)*need*PPM, cy0 - math.sin(th)*need*PPM
        dr.line([x0*SS, y0*SS, x1*SS, y1*SS], fill=col, width=12*SS)
        lx = CX + 210 + 0*i; ly = 330 + i*80
        dr.rectangle([(lx-110)*SS, (ly-30)*SS, (lx+150)*SS, (ly+30)*SS], fill=col)
        text(dr, (lx+20, ly), f"{deg:.0f}°→{lab}", 34, fill=(255, 255, 255))
    dr.rectangle([0, 1040*SS, CW, CH], fill=INK)
    a = ease((t-4.6)/0.6)
    text(dr, (W/2, 1110), "手すりと平行に近づくほど", 40, fill=(255, 255, 255), alpha=a)
    text(dr, (W/2, 1170), "またぐのに必要な長さが伸びる", 40, fill=(255, 255, 255), alpha=a)
    text(dr, (W/2, 1230), "身長170cmでは73°が限界", 36, fill=YEL, alpha=ease((t-5.4)/0.6))
    return im

@scene(6.0)
def result(t):
    im, dr = canvas(INK)
    text(dr, (W/2, 300), "結果", 110, fill=YEL, alpha=ease(t/0.4))
    a = ease((t-1.0)/0.4); b = ease((t-2.0)/0.4)
    text(dr, (W/2 - 60, 520), "その場で", 70, fill=(255, 255, 255), alpha=a)
    if a > 0: text(dr, (W/2 + 200, 520), "○", 110, fill=(80, 200, 255), alpha=a)
    text(dr, (W/2 - 60, 680), "一生くるくる", 70, fill=(255, 255, 255), alpha=b)
    if b > 0: text(dr, (W/2 + 240, 680), "×", 110, fill=RED, alpha=b)
    c = ease((t-3.0)/0.5)
    text(dr, (W/2, 880), f"約{T_FALL:.1f}秒・約{math.degrees(TH_FALL):.0f}°回って落下", 44, fill=(255, 255, 255), alpha=c)
    return im

@scene(3.5)
def caution(t):
    im, dr = canvas(INK)
    a = ease(t/0.5)
    text(dr, (W/2, 580), "※とても危険です", 56, fill=YEL, alpha=a)
    text(dr, (W/2, 670), "絶対にまねしないでください", 50, fill=(255, 255, 255), alpha=a)
    text(dr, (W/2, 820), "体を1本の棒とみなした物理シミュレーションです", 26, fill=(170, 170, 170), black=False, alpha=a)
    return im

# ---------- timeline & audio ----------
starts = np.cumsum([0] + [s[0] for s in scenes])
TOTAL = starts[-1]
SR = 44100
audio = np.zeros(int(SR*(TOTAL+0.5)))
def tone(t0, f, dur, amp=0.4, decay=8.0):
    n = int(dur*SR); tt = np.arange(n)/SR
    sig = amp*np.sin(2*np.pi*f*tt)*np.exp(-decay*tt)
    sig[:200] *= np.linspace(0, 1, 200)
    i = int(t0*SR); audio[i:i+n] += sig[:len(audio)-i]
def thud(t0):
    n = int(0.6*SR); tt = np.arange(n)/SR
    sig = 0.8*np.sin(2*np.pi*(90-50*tt)*tt)*np.exp(-6*tt)
    sig += 0.25*np.random.default_rng(1).normal(size=n)*np.exp(-25*tt)
    i = int(t0*SR); audio[i:i+n] += sig
def ticks(t0, t1, period, f=2200, amp=0.12):
    t = t0
    while t < t1: tone(t, f, 0.03, amp, 120); t += period

S = dict(zip([fn.__name__ for _, fn in scenes], starts[:-1]))
tone(S["title"]+1.9, 660, 0.6, 0.3, 4); tone(S["title"]+2.0, 990, 0.8, 0.25, 3)
for k in range(3): tone(S["countdown"]+k, 880, 0.25, 0.4, 10)
tone(S["countdown"]+3, 1760, 0.6, 0.45, 5)
ticks(S["realtime"], S["realtime"]+T_FALL, 0.1)
thud(S["realtime"]+T_FALL)
ticks(S["slowmo"], S["slowmo"]+T_FALL*SLOW, 0.1*SLOW/2, f=1500)
thud(S["slowmo"]+T_FALL*SLOW)
tone(S["result"]+1.0, 1046, 0.7, 0.35, 4); tone(S["result"]+1.08, 1318, 0.7, 0.3, 4)
tone(S["result"]+2.0, 220, 0.6, 0.45, 5); tone(S["result"]+2.0, 233, 0.6, 0.4, 5)
audio = np.clip(audio, -1, 1)
with wave.open("audio.wav", "wb") as wf:
    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
    wf.writeframes((audio*32000).astype(np.int16).tobytes())

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "preview":
        for name, tl in [("title", 3.5), ("setup", 6), ("realtime", 0.6), ("realtime", 3.5),
                         ("slowmo", 6), ("slowmo", 11.5), ("why", 6.5), ("result", 5)]:
            fn = dict((f.__name__, f) for _, f in scenes)[name]
            fn(tl).resize((W, H), Image.LANCZOS).save(f"pv_{name}_{tl}.png")
        sys.exit()
    nfr = int(TOTAL*FPS)
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", "audio.wav",
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                          "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                          "dosoku_kaiten_jikken.mp4"], stdin=subprocess.PIPE)
    idx = 0
    for f in range(nfr):
        t = f/FPS
        while idx < len(scenes)-1 and t >= starts[idx+1]: idx += 1
        im = scenes[idx][1](t - starts[idx]).resize((W, H), Image.LANCZOS)
        p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()
    print("total", TOTAL, "frames", nfr)
