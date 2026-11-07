"""絵本アニメ風の背景 × 超リアルなキリン版。物理(sim.py)・数値・文言・尺は render.py と同一。
使い方:
  python3 render_giraffe.py preview     確認用の静止画 (pv_g_*.png)
  python3 render_giraffe.py check       文字色のコントラスト比を表示
  python3 render_giraffe.py             本番書き出し -> dosoku_kaiten_giraffe.mp4
素材:
  giraffe.png            真上から見た透過PNG(頭が右向き・ほぼ一直線)。無ければ仮キリンを自動生成
  giraffe_meta.json      任意。{"tail_x":..,"nose_x":..,"axis_y":..,"rotate":deg} 尾の付け根/鼻先/体軸のpx座標
  narration/line01..13   任意。wav/mp3/m4a。あれば自動で配置・効果音を-8dB・-14LUFSに整える
"""
import numpy as np, subprocess, wave, math, os, json, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from sim import d, v, L, mu

HERE = os.path.dirname(os.path.abspath(__file__))
W, H, SS, FPS = 720, 1280, 2, 30
CW, CH = W*SS, H*SS
FB = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"
FM = FB
_fc = {}
def font(size, black=True):
    k = (size, black)
    if k not in _fc:
        _fc[k] = ImageFont.truetype(FB if black else FM, size*SS, index=0)
    return _fc[k]

# ---- palette (絵本風) ----
INK = (74, 59, 50)            # #4a3b32 焦げ茶(線・文字・パネル)
PAPER = (250, 243, 226)       # 生成り
LIGHT = (246, 238, 224)       # 焦げ茶パネル上の文字
LIGHT2 = (226, 214, 196)      # パネル上の項目名
SHU = (200, 55, 35)           # 朱色
YAMA = (244, 190, 60)         # 山吹色
YEL = (255, 212, 0)           # 元仕様の黄色(中心の十字)
RED = (230, 50, 40)           # 元仕様の赤(力の矢印)
BLU = (40, 110, 230)          # why の 0° の線
PUR = (110, 80, 200)
NAVY = (34, 46, 102)          # 手すり(ゴム)
NAVY_HI = (62, 80, 148)
GAPC = (66, 52, 104)          # すき間: 影の青紫
TRAIL = (140, 165, 220)       # 回転の残像(元仕様の色)
BLUE_OK = (30, 110, 160)

traj = np.load(os.path.join(HERE, "traj.npy"))
DT = 1e-4
T_FALL = traj[-1, 0]
TH_FALL = traj[-1, 3]
def state(ts):
    i = min(int(round(ts/DT)), len(traj)-1)
    return traj[i]
def ease(x): x = min(max(x, 0), 1); return x*x*(3-2*x)

# ---------- 手描き風プリミティブ ----------
def wobble_pts(pts, seg=26, j=1.5, seed=0):
    rng = np.random.default_rng(seed)
    out = []
    for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
        n = max(1, int(math.hypot(x1-x0, y1-y0)/(seg*SS)))
        for i in range(n):
            t = i/n
            out.append((x0+(x1-x0)*t + rng.uniform(-j, j)*SS, y0+(y1-y0)*t + rng.uniform(-j, j)*SS))
    out.append((pts[-1][0] + rng.uniform(-j, j)*SS, pts[-1][1] + rng.uniform(-j, j)*SS))
    return out

def wline(dr, pts, fill, width, seed=0, j=1.5, seg=26):
    p = wobble_pts(pts, seg, j, seed)
    w = max(1, int(width*SS))
    dr.line(p, fill=fill, width=w, joint="curve")
    r = w/2
    for q in (p[0], p[-1]):
        dr.ellipse([q[0]-r, q[1]-r, q[0]+r, q[1]+r], fill=fill)

def rrect_pts(x0, y0, x1, y1, r, n=7):
    pts = []
    for cx, cy, a0 in ((x1-r, y0+r, -90), (x1-r, y1-r, 0), (x0+r, y1-r, 90), (x0+r, y0+r, 180)):
        for i in range(n+1):
            a = math.radians(a0 + 90*i/n)
            pts.append((cx + r*math.cos(a), cy + r*math.sin(a)))
    return pts

def hand_shape(dr, pts, fill, outline=INK, ow=3, seed=0, j=1.5, seg=30):
    p = wobble_pts(pts + [pts[0]], seg, j, seed)[:-1]
    if fill is not None:
        dr.polygon(p, fill=fill)
    if outline is not None:
        dr.line(p + [p[0], p[1]], fill=outline, width=int(ow*SS), joint="curve")

def board(dr, x0, y0, x1, y1, fill=INK, outline=None, r=26, seed=1, ow=3):
    """角丸の板(px は出力座標)"""
    pts = rrect_pts(x0*SS, y0*SS, x1*SS, y1*SS, r*SS)
    hand_shape(dr, pts, fill, outline, ow, seed, j=1.0, seg=40)

def text(dr, xy, s, size, fill=INK, black=True, anchor="mm", alpha=1.0, stroke=0, stroke_fill=None):
    """IPAゴシックは1ウェイトのみ。black=True は縁取りで太字風にする。alpha は紙の上でも自然に重なる"""
    x, y = xy
    f = font(size, black)
    bold = max(1, int(size*SS/45)) if black else 0
    sw = stroke*SS
    pad = sw + bold + 6*SS
    l, t, r, b = dr.textbbox((x*SS, y*SS), s, font=f, anchor=anchor, stroke_width=sw+bold)
    w, h = int(r-l)+2*pad, int(b-t)+2*pad
    base_c = stroke_fill if sw else fill
    layer = Image.new("RGBA", (w, h), tuple(base_c) + (0,))
    ld = ImageDraw.Draw(layer)
    pos = (x*SS-l+pad, y*SS-t+pad)
    if sw:
        ld.text(pos, s, font=f, fill=stroke_fill, anchor=anchor, stroke_width=sw+bold, stroke_fill=stroke_fill)
        # 本体の色で上書きするため内側のレイヤーを別に作る
        inner = Image.new("RGBA", (w, h), tuple(fill) + (0,))
        idr = ImageDraw.Draw(inner)
        idr.text(pos, s, font=f, fill=fill, anchor=anchor, stroke_width=bold, stroke_fill=fill if bold else None)
        layer.paste(inner, (0, 0), inner.split()[3])
    else:
        ld.text(pos, s, font=f, fill=fill, anchor=anchor, stroke_width=bold, stroke_fill=fill if bold else None)
    a = layer.split()[3]
    if alpha < 1:
        a = a.point(lambda q: int(q*alpha))
    dr._im.paste(layer.convert("RGB"), (int(l-pad), int(t-pad)), a)

def marker_band(dr, cx, cy, w, h, seed=0, color=(250, 218, 120)):
    """蛍光ペン風の山吹色の帯(強調文字の下)"""
    pts = [(cx*SS-w*SS/2, cy*SS-h*SS/2), (cx*SS+w*SS/2, cy*SS-h*SS/2),
           (cx*SS+w*SS/2, cy*SS+h*SS/2), (cx*SS-w*SS/2, cy*SS+h*SS/2)]
    hand_shape(dr, pts, color, None, 0, seed, j=3.0, seg=60)

# ---------- 紙・水彩の質感 ----------
def lowfreq(w, h, cells, seed):
    rng = np.random.default_rng(seed)
    n = rng.random((max(2, int(cells*h/w)), cells)).astype(np.float32)
    im = Image.fromarray((n*255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    return np.asarray(im, np.float32)/255

def paper_array():
    qw, qh = CW//4, CH//4
    base = np.array(PAPER, np.float32)[None, None, :]*np.ones((qh, qw, 1), np.float32)
    n1, n2 = lowfreq(qw, qh, 5, 3), lowfreq(qw, qh, 12, 4)
    peach = np.array([252, 224, 196], np.float32); sage = np.array([222, 238, 224], np.float32)
    m1 = np.clip((n1-0.5)*2.4, 0, 1)[..., None]*0.50
    m2 = np.clip((n2-0.55)*2.6, 0, 1)[..., None]*0.38
    img = base*(1-m1) + peach*m1
    img = img*(1-m2) + sage*m2
    big = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((CW, CH), Image.BICUBIC)
    a = np.asarray(big, np.float32)
    grain = np.random.default_rng(7).normal(0, 1, (CH, CW)).astype(np.float32)*(0.03*255*0.5)  # 約3%
    return a + grain[..., None]

_PAPER = None
def paper():
    global _PAPER
    if _PAPER is None:
        _PAPER = Image.fromarray(np.clip(paper_array(), 0, 255).astype(np.uint8))
    return _PAPER

def canvas():
    im = paper().copy()
    dr = ImageDraw.Draw(im); dr._im = im
    return im, dr

# ---------- 上から見た舞台 ----------
PPM = 330
CX, CY = W/2, 600
def w2s(x, y): return ((CX + x*PPM)*SS, (CY - y*PPM)*SS)
TOP, BOT = 120, 1080

def rail_shape(dr, xr, top, bot, hw, seed):
    pts = rrect_pts((xr-hw)*SS, top*SS, (xr+hw)*SS, bot*SS, min(hw, 12)*SS, n=5)
    hand_shape(dr, pts, NAVY, INK, 3, seed, j=1.0, seg=50)
    wline(dr, [((xr-hw*0.35)*SS, (top+14)*SS), ((xr-hw*0.35)*SS, (bot-14)*SS)], NAVY_HI, 3, seed+5, j=0.8, seg=60)

_STAGE = None
def stage_base():
    """床(クリーム〜ミント)+すき間(青紫)+手すり(紺)を、水彩のにじみ付きで1回だけ作る"""
    global _STAGE
    if _STAGE is not None: return _STAGE
    a = paper_array()
    gx0, gx1 = CX - d/2*PPM + 14, CX + d/2*PPM - 14
    fl_l = (-4, TOP, CX - (d/2*PPM + 14), BOT)
    fl_r = (CX + (d/2*PPM + 14), TOP, W+4, BOT)
    def mask(rects):
        m = Image.new("L", (CW, CH), 0); md = ImageDraw.Draw(m)
        for x0, y0, x1, y1 in rects:
            md.rectangle([x0*SS, y0*SS, x1*SS, y1*SS], fill=255)
        return m
    qw, qh = CW//4, CH//4
    mott = np.asarray(Image.fromarray((lowfreq(qw, qh, 7, 11)*255).astype(np.uint8)).resize((CW, CH), Image.BICUBIC), np.float32)/255
    for rects, c0, c1 in (([fl_l, fl_r], (248, 240, 208), (208, 236, 220)), ([(gx0, TOP, gx1, BOT)], (74, 58, 118), (56, 48, 96))):
        m = mask(rects).filter(ImageFilter.GaussianBlur(1.6*SS))
        mf = np.asarray(m, np.float32)/255
        mb = np.asarray(m.filter(ImageFilter.GaussianBlur(11*SS)), np.float32)/255
        pool = np.clip(mf - mb, 0, 1)[..., None]          # ふちに絵の具がたまる
        col = np.array(c0, np.float32)*(1-mott[..., None]) + np.array(c1, np.float32)*mott[..., None]
        col = col*(1 - 0.55*pool)
        a = a*(1-mf[..., None]) + col*mf[..., None]
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    dr = ImageDraw.Draw(im)
    for k, (x0, y0, x1, y1) in enumerate((fl_l, fl_r)):
        wline(dr, [(x0*SS, y0*SS), (x1*SS, y0*SS), (x1*SS, y1*SS), (x0*SS, y1*SS), (x0*SS, y0*SS)], INK, 3, seed=20+k)
    for k, side in enumerate((-1, 1)):
        rail_shape(dr, CX + side*d/2*PPM, TOP, BOT, 14, 30+k)
    _STAGE = im
    return im

def stage_canvas():
    im = stage_base().copy()
    dr = ImageDraw.Draw(im); dr._im = im
    return im, dr

def draw_stage_dyn(dr, ts):
    """動く部分: 溝(少し波打つ)・進行方向の矢印・手すりの目印(山吹の丸い点)"""
    for side, sgn in ((-1, -1), (1, 1)):
        x0 = CX + side*(d/2*PPM + 14); x1 = CX + side*W
        xa, xb = sorted((x0, x1)); xa = max(xa, 4); xb = min(xb, W-4)
        off = (sgn*v*ts*PPM) % 22
        y = TOP - 22 + off; k = 0
        while y < BOT:
            if TOP+4 < y < BOT-4:
                pts = []
                x = xa
                while x < xb:
                    pts.append((x*SS, (y + 2.4*math.sin(x/21.0 + k*0.9))*SS)); x += 24
                pts.append((xb*SS, (y + 2.4*math.sin(xb/21.0 + k*0.9))*SS))
                wline(dr, pts, (176, 206, 176), 3, seed=(k % 22)+100, j=0.6, seg=1000)
            y += 22; k += 1
        ax = CX + side*(d/2*PPM + 110)
        for k in range(4):
            yy = TOP + ((k*240 - sgn*v*ts*PPM) % 960)
            tip = -sgn*26
            if yy - 30 < TOP+6 or yy + 30 > BOT-6: continue
            tri = [(ax*SS, (yy+tip)*SS), ((ax-18)*SS, (yy-tip*0.2)*SS), ((ax+18)*SS, (yy-tip*0.2)*SS)]
            hand_shape(dr, tri, (172, 210, 178), INK, 3, seed=200+k, j=0.8, seg=20)
            for q in tri:  # 角を丸く見せる
                dr.ellipse([q[0]-1.5*SS, q[1]-1.5*SS, q[0]+1.5*SS, q[1]+1.5*SS], fill=INK)
    for side, sgn in ((-1, -1), (1, 1)):
        xr = CX + side*d/2*PPM
        off = (sgn*v*ts*PPM) % 40
        y = TOP - 40 + off
        while y < BOT:
            if TOP+10 < y < BOT-10:
                r = 5.5*SS
                dr.ellipse([xr*SS-r, y*SS-r, xr*SS+r, y*SS+r], fill=YAMA, outline=INK, width=2)
            y += 40
    # はみ出しを紙で隠す(上下の帯)
    base = stage_base()
    dr._im.paste(base.crop((0, 0, CW, (TOP-4)*SS)), (0, 0))
    dr._im.paste(base.crop((0, (BOT+4)*SS, CW, CH)), (0, (BOT+4)*SS))

# ---------- キリン ----------
def make_placeholder(path):
    """【仮】実写キリンの透過PNGが届くまでの検証用ダミー。最終版ではない"""
    Wd, Hd = 2000, 640
    im = Image.new("RGBA", (Wd, Hd), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    sil = Image.new("L", (Wd, Hd), 0); sd = ImageDraw.Draw(sil)
    sd.ellipse([20, 150, 1000, 490], fill=255)                       # 胴
    sd.polygon([(900, 255), (1620, 290), (1620, 350), (900, 385)], fill=255)  # 首
    sd.ellipse([1560, 262, 1990, 378], fill=255)                     # 頭
    for yy in (170, 450): sd.ellipse([260, yy-30, 640, yy+30], fill=255)  # 脚
    sil = sil.filter(ImageFilter.GaussianBlur(1.2))
    body = Image.new("RGBA", (Wd, Hd), (214, 172, 96, 255))
    bd = ImageDraw.Draw(body); rng = np.random.default_rng(5)
    for _ in range(95):
        cx, cy = rng.uniform(40, 1950), rng.uniform(150, 490); r = rng.uniform(26, 58)
        pts = [(cx + r*math.cos(a)*rng.uniform(.7, 1.2), cy + r*math.sin(a)*rng.uniform(.7, 1.2)) for a in np.linspace(0, 2*math.pi, 8, endpoint=False)]
        bd.polygon(pts, fill=(138, 84, 40, 255))
    im.paste(body, (0, 0), sil)
    im.save(path)

class Giraffe:
    def __init__(self):
        gp = os.path.join(HERE, "giraffe.png")
        self.placeholder = not os.path.exists(gp)
        if self.placeholder:
            gp = os.path.join(HERE, "giraffe_placeholder.png")
            if not os.path.exists(gp): make_placeholder(gp)
        img = Image.open(gp).convert("RGBA")
        meta = {}
        mp = os.path.join(HERE, "giraffe_meta.json")
        if os.path.exists(mp): meta = json.load(open(mp))
        if meta.get("rotate"):
            img = img.convert("RGBa").rotate(meta["rotate"], expand=True, resample=Image.BICUBIC).convert("RGBA")
        al = np.asarray(img)[..., 3]
        ys, xs = np.where(al > 24)
        tail_x = meta.get("tail_x", xs.min()); nose_x = meta.get("nose_x", xs.max())
        axis_y = meta.get("axis_y", (ys.min() + ys.max())/2)
        s = (L*PPM*SS)/(nose_x - tail_x)                     # 体の軸 = L=1.70m
        pm = img.convert("RGBa").resize((max(1, round(img.width*s)), max(1, round(img.height*s))), Image.LANCZOS)
        mx, my = (tail_x + nose_x)/2*s, axis_y*s
        R = int(max(mx, pm.width-mx, my, pm.height-my)) + 6
        sq = Image.new("RGBa", (2*R, 2*R), (0, 0, 0, 0)); sq.paste(pm, (R-int(mx), R-int(my)))
        self.R, self.sq = R, sq
        # やわらかい楕円の影(不透明度30%・ぼかし大)
        RS = R + 60*SS                                        # ぼかしが切れないよう余白を多めに
        sh = Image.new("L", (2*RS, 2*RS), 0); sd = ImageDraw.Draw(sh)
        hl, hw = L*PPM*SS*0.50, 0.21*PPM*SS
        sd.ellipse([RS-hl, RS-hw, RS+hl, RS+hw], fill=255)
        self.shadow = sh.filter(ImageFilter.GaussianBlur(15*SS)).point(lambda q: int(q*0.30))

    def draw(self, dr, xc, yc, th, scale=1.0, k=0.0):
        im = dr._im
        px, py = w2s(xc, yc)
        deg = math.degrees(th)
        def prep(src, mode):
            s2 = src
            if scale != 1.0:
                n = max(2, round(src.width*scale)); s2 = src.resize((n, n), Image.BICUBIC)
            return s2.rotate(deg, resample=Image.BICUBIC)
        rs = prep(self.shadow, "L")
        ox, oy = 4*SS*scale, 7*SS*scale
        im.paste((38, 28, 22), (int(px - rs.width/2 + ox), int(py - rs.height/2 + oy)), rs)
        rg = prep(self.sq, "RGBa").convert("RGBA")
        rgb, a = rg.convert("RGB"), rg.split()[3]
        if k > 0:
            rgb = Image.blend(rgb, Image.new("RGB", rgb.size, (90, 90, 100)), 0.8*k)
        im.paste(rgb, (int(px - rg.width/2), int(py - rg.height/2)), a)

_G = None
def giraffe():
    global _G
    if _G is None: _G = Giraffe()
    return _G

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
    draw_stage_dyn(dr, ts)
    if trails:
        k = 0.15
        while k < min(ts, T_FALL):
            s2 = state(k); c, sn = math.cos(s2[3]), math.sin(s2[3])
            wline(dr, [w2s(s2[1]-c*L/2, s2[2]-sn*L/2), w2s(s2[1]+c*L/2, s2[2]+sn*L/2)],
                  TRAIL, 5, seed=int(k*100), j=1.0, seg=60)
            k += 0.15
    if not fell:
        giraffe().draw(dr, st[1], st[2], st[3])
        if forces:
            for si, fx, fy in ((st[7], st[9], st[10]), (st[8], st[11], st[12])):
                px = st[1] + si*math.cos(st[3]); py = st[2] + si*math.sin(st[3])
                p = w2s(px, py)
                sc = 0.9*SS
                arrow(dr, p, (fx*sc, -fy*sc), RED)
                dr.ellipse([p[0]-9*SS, p[1]-9*SS, p[0]+9*SS, p[1]+9*SS], fill=RED)
    else:
        k = ease((ts - T_FALL)/0.35)
        giraffe().draw(dr, st[1], st[2], st[3] + 0.15*k, scale=1 - 0.35*k, k=k)
    if center:
        p = w2s(st[1], st[2])
        dr.line([p[0]-22*SS, p[1], p[0]+22*SS, p[1]], fill=YEL, width=5*SS)
        dr.line([p[0], p[1]-22*SS, p[0], p[1]+22*SS], fill=YEL, width=5*SS)
    if hud:
        # 経過時間・回転した角度のパネル(数値・項目名・位置・サイズは元のまま、見た目だけ角丸の焦げ茶板)
        board(dr, 24, 1092, 356, 1262, seed=41)
        board(dr, 364, 1092, 696, 1262, seed=42)
        tshow = min(ts, T_FALL)
        text(dr, (190, 1150), "経過時間", 30, fill=LIGHT2, black=False)
        text(dr, (190, 1215), f"{tshow:4.2f} 秒", 62, fill=LIGHT)
        text(dr, (530, 1150), "回転した角度", 30, fill=LIGHT2, black=False)
        text(dr, (530, 1215), f"{math.degrees(st[3]):4.1f}°", 62, fill=YAMA)
    if slow_label:
        board(dr, 14, 10, W-14, 112, seed=43)
        text(dr, (W/2, 60), slow_label, 44, fill=LIGHT)

# ---------- scenes ----------
scenes = []
def scene(dur):
    def deco(fn): scenes.append((dur, fn)); return fn
    return deco

@scene(5.0)
def title(t):
    im, dr = canvas()
    a1, a2, a3 = ease(t/0.6), ease((t-0.9)/0.6), ease((t-1.9)/0.5)
    text(dr, (W/2, 330), "実験", 40, fill=SHU, alpha=a1)
    text(dr, (W/2, 470), "動く歩道の手すりに", 58, fill=INK, alpha=a1)
    text(dr, (W/2, 560), "またがって寝転んだら", 58, fill=INK, alpha=a2)
    if t > 1.9:
        sz = int(76 + 30*(1-a3))
        marker_band(dr, W/2, 740, 400, 100, seed=1)
        marker_band(dr, W/2, 860, 640, 100, seed=2)
        text(dr, (W/2, 740), "一生", sz, fill=SHU)
        text(dr, (W/2, 860), "くるくる回るのか？", sz, fill=SHU)
    return im

@scene(7.0)
def setup(t):
    im, dr = stage_canvas()
    draw_stage_dyn(dr, t)
    a = ease((t-0.8)/0.6)
    if a > 0:
        giraffe().draw(dr, 0, 0, 0)
    y = CY + 210
    x0, x1 = (CX - d/2*PPM)*SS, (CX + d/2*PPM)*SS
    wline(dr, [(x0, y*SS), (x1, y*SS)], SHU, 5, seed=61)
    for x in (x0, x1): wline(dr, [(x, (y-18)*SS), (x, (y+18)*SS)], SHU, 5, seed=int(x) % 97)
    board(dr, CX-80, y+24, CX+80, y+80, fill=PAPER, outline=INK, r=16, seed=62)
    text(dr, (CX, y+52), "50cm", 40, fill=SHU)
    board(dr, 14, 10, W-14, 112, seed=63)
    text(dr, (W/2, 60), "実験の条件（上から見た図）", 44, fill=LIGHT)
    board(dr, 14, 1092, W-14, 1266, seed=64)
    rows = ["手すりの速さ：分速40m（逆向き）", "身長170cm・体はまっすぐな棒として計算", "手すりの摩擦係数：0.6"]
    for i, r in enumerate(rows):
        al = ease((t-1.5-i*0.9)/0.5)
        text(dr, (W/2, 1125+i*58), r, 34, fill=LIGHT, black=False, alpha=al)
    return im

@scene(4.0)
def countdown(t):
    im, dr = canvas()
    if t < 3.0:
        n = 3 - int(t)
        k = t - int(t)
        text(dr, (W/2, H/2), str(n), int(300 - 60*k), fill=INK)
        text(dr, (W/2, 330), "実験開始まで", 44, fill=SHU)
    else:
        marker_band(dr, W/2, H/2, 560, 150, seed=3)
        text(dr, (W/2, H/2), "スタート", 120, fill=SHU)
    return im

REAL_HOLD = 3.0
@scene(T_FALL + REAL_HOLD)
def realtime(t):
    im, dr = stage_canvas()
    sim_view(dr, t, slow_label="実際の速さ")
    if t > T_FALL:
        k = ease((t-T_FALL)/0.25)
        board(dr, W/2-230, 520, W/2+230, 680, fill=SHU, outline=INK, r=30, seed=71)
        text(dr, (W/2, 600), "落下！", int(80+40*(1-k)), fill=(255, 255, 255))
    if t > T_FALL + 1.2:
        text(dr, (W/2, 940), "一瞬で落ちた…", 52, fill=INK, stroke=5, stroke_fill=PAPER)
    return im

@scene(2.5)
def slowcard(t):
    im, dr = canvas()
    text(dr, (W/2, 560), "スローで", 90, fill=INK, alpha=ease(t/0.4))
    text(dr, (W/2, 700), "見てみよう", 90, fill=INK, alpha=ease((t-0.4)/0.4))
    text(dr, (W/2, 850), "（8分の1の速さ）", 40, fill=SHU, alpha=ease((t-0.8)/0.4))
    return im

SLOW = 8.0
@scene(T_FALL*SLOW + 4.0)
def slowmo(t):
    im, dr = stage_canvas()
    ts = t/SLOW if t < T_FALL*SLOW else T_FALL + (t - T_FALL*SLOW)
    sim_view(dr, ts, trails=True, forces=True, center=True, slow_label="スロー 1/8倍速")
    cap = None
    if 0.5 < t < 4.0: cap = "赤い矢印＝手すりが体を引っぱる力"
    elif 4.0 < t < 8.0: cap = "左右で逆向き → 体が回り出す"
    elif 8.0 < t < T_FALL*SLOW: cap = "黄色の十字＝体の中心は動かない"
    elif t > T_FALL*SLOW + 0.3: cap = "約73°回ったところで落下"
    if cap:
        board(dr, 14, 126, W-14, 202, fill=PAPER, outline=INK, r=22, seed=81)
        text(dr, (W/2, 164), cap, 36, fill=INK)
    return im

@scene(7.0)
def why(t):
    im, dr = canvas()
    board(dr, 14, 10, W-14, 112, seed=91)
    text(dr, (W/2, 60), "なぜ一生は回れないのか", 46, fill=LIGHT)
    top, bot = 260, 1000
    for k, side in enumerate((-1, 1)):
        rail_shape(dr, CX + side*d/2*PPM, top, bot, 12, 95+k)
    cy0 = 630
    items = [(0, "50cm", BLU), (45, "71cm", PUR), (72.9, "170cm", RED)]
    for i, (deg, lab, col) in enumerate(items):
        a = ease((t - 0.4 - i*1.4)/0.5)
        if a <= 0: continue
        th = math.radians(deg)
        need = d/math.cos(th)/2
        x0, y0 = CX - math.cos(th)*need*PPM, cy0 + math.sin(th)*need*PPM
        x1, y1 = CX + math.cos(th)*need*PPM, cy0 - math.sin(th)*need*PPM
        wline(dr, [(x0*SS, y0*SS), (x1*SS, y1*SS)], col, 12, seed=110+i, j=1.5, seg=30)
        lx = CX + 210; ly = 330 + i*80
        board(dr, lx-110, ly-30, lx+150, ly+30, fill=col, outline=INK, r=16, seed=120+i)
        text(dr, (lx+20, ly), f"{deg:.0f}°→{lab}", 34, fill=(255, 255, 255))
    board(dr, 14, 1048, W-14, 1266, seed=130)
    a = ease((t-4.6)/0.6)
    text(dr, (W/2, 1110), "手すりと平行に近づくほど", 40, fill=LIGHT, alpha=a)
    text(dr, (W/2, 1170), "またぐのに必要な長さが伸びる", 40, fill=LIGHT, alpha=a)
    text(dr, (W/2, 1230), "身長170cmでは73°が限界", 36, fill=YAMA, alpha=ease((t-5.4)/0.6))
    return im

@scene(6.0)
def result(t):
    im, dr = canvas()
    text(dr, (W/2, 300), "結果", 110, fill=SHU, alpha=ease(t/0.4))
    a = ease((t-1.0)/0.4); b = ease((t-2.0)/0.4)
    text(dr, (W/2 - 60, 520), "その場で", 70, fill=INK, alpha=a)
    if a > 0: text(dr, (W/2 + 200, 520), "○", 110, fill=BLUE_OK, alpha=a)
    text(dr, (W/2 - 60, 680), "一生くるくる", 70, fill=INK, alpha=b)
    if b > 0: text(dr, (W/2 + 240, 680), "×", 110, fill=SHU, alpha=b)
    c = ease((t-3.0)/0.5)
    text(dr, (W/2, 880), f"約{T_FALL:.1f}秒・約{math.degrees(TH_FALL):.0f}°回って落下", 44, fill=INK, alpha=c)
    return im

@scene(3.5)
def caution(t):
    im, dr = canvas()
    a = ease(t/0.5)
    text(dr, (W/2, 580), "※とても危険です", 56, fill=SHU, alpha=a)
    text(dr, (W/2, 670), "絶対にまねしないでください", 50, fill=INK, alpha=a)
    text(dr, (W/2, 820), "体を1本の棒とみなした物理シミュレーションです", 26, fill=(110, 90, 78), black=False, alpha=a)
    return im

# ---------- コントラスト確認 ----------
def _lum(c):
    f = lambda u: (u/255/12.92) if u/255 <= 0.03928 else (((u/255)+0.055)/1.055)**2.4
    r, g, b = c; return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)
def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True); return (la+0.05)/(lb+0.05)
CHECKS = [
    ("パネル上: 時間/文言", LIGHT, INK, 4.5), ("パネル上: 項目名", LIGHT2, INK, 4.5), ("パネル上: 角度(山吹)", YAMA, INK, 4.5),
    ("紙上: 本文", INK, PAPER, 4.5), ("紙上: 朱色(大文字)", SHU, PAPER, 3.0), ("帯上: 朱色(大文字)", SHU, (250, 218, 120), 3.0),
    ("紙上: ○", BLUE_OK, PAPER, 3.0), ("紙上: 注意書き小文字", (110, 90, 78), PAPER, 4.5),
    ("落下！(白/朱)", (255, 255, 255), SHU, 3.0), ("why 0°ラベル(白/青)", (255, 255, 255), BLU, 3.0),
    ("why 45°ラベル(白/紫)", (255, 255, 255), PUR, 3.0), ("why 73°ラベル(白/赤)", (255, 255, 255), RED, 3.0),
    ("50cm(朱/紙箱)", SHU, PAPER, 3.0),
]
def run_check():
    bad = 0
    for n, f, b, need in CHECKS:
        c = contrast(f, b); ok = c >= need; bad += (not ok)
        print(f"{'OK ' if ok else 'NG '} {c:5.2f} (>= {need})  {n}")
    return bad

# ---------- 音声 ----------
starts = np.cumsum([0] + [s[0] for s in scenes])
TOTAL = starts[-1]
SR = 44100
S = dict(zip([fn.__name__ for _, fn in scenes], starts[:-1]))
DUR = dict(zip([fn.__name__ for _, fn in scenes], [s[0] for s in scenes]))
NARR = [("title", 0.3), ("setup", 0.5), ("setup", 4.0), ("realtime", 1.4), ("slowcard", 0.2),
        ("slowmo", 0.5), ("slowmo", 4.2), ("slowmo", 8.2), ("slowmo", 10.0),
        ("why", 0.5), ("why", 4.8), ("result", 0.8), ("caution", 0.2)]

def build_sfx():
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
    tone(S["title"]+1.9, 660, 0.6, 0.3, 4); tone(S["title"]+2.0, 990, 0.8, 0.25, 3)
    for k in range(3): tone(S["countdown"]+k, 880, 0.25, 0.4, 10)
    tone(S["countdown"]+3, 1760, 0.6, 0.45, 5)
    ticks(S["realtime"], S["realtime"]+T_FALL, 0.1)
    thud(S["realtime"]+T_FALL)
    ticks(S["slowmo"], S["slowmo"]+T_FALL*SLOW, 0.1*SLOW/2, f=1500)
    thud(S["slowmo"]+T_FALL*SLOW)
    tone(S["result"]+1.0, 1046, 0.7, 0.35, 4); tone(S["result"]+1.08, 1318, 0.7, 0.3, 4)
    tone(S["result"]+2.0, 220, 0.6, 0.45, 5); tone(S["result"]+2.0, 233, 0.6, 0.4, 5)
    return np.clip(audio, -1, 1)

def load_voice(path, tempo=1.0):
    cmd = ["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR)]
    if tempo > 1.001: cmd += ["-af", f"atempo={tempo:.4f}"]
    cmd += ["-f", "s16le", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float64)/32768

def find_voice(i):
    for ext in ("wav", "mp3", "m4a", "aiff", "ogg"):
        p = os.path.join(HERE, "narration", f"line{i+1:02d}.{ext}")
        if os.path.exists(p): return p
    return None

def build_audio():
    sfx = build_sfx()
    voices = []
    for i, (sc, off) in enumerate(NARR):
        p = find_voice(i)
        if not p: continue
        t0 = S[sc] + off
        nxt = [o for s2, o in NARR[i+1:i+2] if s2 == sc]
        end = S[sc] + (nxt[0] if nxt else DUR[sc]) - 0.1
        x = load_voice(p)
        win = end - t0
        if len(x)/SR > win:                       # はみ出す場合は話す速さを上げる
            tempo = min(1.5, (len(x)/SR)/win)
            x = load_voice(p, tempo)
            print(f"line{i+1:02d}: {len(x)/SR:.2f}s (tempo x{tempo:.2f}, window {win:.2f}s)")
        voices.append((t0, x))
    if not voices: return sfx, False
    duck = np.ones(len(sfx))
    for t0, x in voices:
        duck[int(t0*SR):int(t0*SR)+len(x)] = 10**(-8/20)
    k = int(0.05*SR); duck = np.convolve(duck, np.ones(k)/k, mode="same")   # 50ms でなめらかに
    mix = sfx*duck
    for t0, x in voices:
        i = int(t0*SR); mix[i:i+len(x)] += x[:len(mix)-i]
    return np.clip(mix, -1, 1), True

# ---------- main ----------
if __name__ == "__main__":
    arg = sys.argv[1] if len(sys.argv) > 1 else "render"
    if arg == "check":
        sys.exit(1 if run_check() else 0)
    if arg == "preview":
        fns = dict((f.__name__, f) for _, f in scenes)
        shots = [("title", 3.5), ("setup", 6), ("countdown", 1.5), ("realtime", 0.6), ("realtime", 3.5),
                 ("slowcard", 2.0), ("slowmo", 0.75*SLOW), ("slowmo", T_FALL*SLOW-0.05), ("slowmo", 11.5),
                 ("why", 6.5), ("result", 5), ("caution", 2)]
        for name, tl in shots:
            fns[name](tl).resize((W, H), Image.LANCZOS).save(os.path.join(HERE, f"pv_g_{name}_{tl:.2f}.png"))
        print("placeholder giraffe:", giraffe().placeholder)
        sys.exit()
    audio, has_voice = build_audio()
    with wave.open(os.path.join(HERE, "audio_giraffe.wav"), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((audio*32000).astype(np.int16).tobytes())
    af = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"] if has_voice else []
    nfr = int(TOTAL*FPS)
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", os.path.join(HERE, "audio_giraffe.wav"),
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                          *af, "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                          os.path.join(HERE, "dosoku_kaiten_giraffe.mp4")], stdin=subprocess.PIPE)
    idx = 0
    for f in range(nfr):
        t = f/FPS
        while idx < len(scenes)-1 and t >= starts[idx+1]: idx += 1
        im = scenes[idx][1](t - starts[idx]).resize((W, H), Image.LANCZOS)
        p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()
    print("total", TOTAL, "frames", nfr, "voice", has_voice, "placeholder giraffe", giraffe().placeholder)
