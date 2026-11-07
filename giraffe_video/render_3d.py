"""絵本アニメ風の背景 × 超リアルなキリン版。物理(sim.py)・数値・文言・尺は render.py と同一。
使い方:
  python3 render_giraffe.py preview     確認用の静止画 (pv_3_*.png)
  python3 render_giraffe.py check       文字色のコントラスト比を表示
  python3 render_giraffe.py             本番書き出し -> dosoku_kaiten_3d_full.mp4
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
PAPER = (255, 246, 226)       # 生成り
LIGHT = (246, 238, 224)       # 焦げ茶パネル上の文字
LIGHT2 = (226, 214, 196)      # パネル上の項目名
SHU = (192, 46, 28)           # 朱色
YAMA = (255, 200, 60)         # 山吹色
YEL = (255, 212, 0)           # 元仕様の黄色(中心の十字)
RED = (230, 50, 40)           # 元仕様の赤(力の矢印)
BLU = (40, 110, 230)          # why の 0° の線
PUR = (110, 80, 200)
NAVY = (52, 88, 190)          # 手すり(ゴム)
NAVY_HI = (130, 168, 240)
GAPC = (92, 84, 150)          # すき間: 影の青紫
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
    rng = np.random.default_rng(seed); j = 0
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

def drop_shadow(dr, x0, y0, x1, y1, r, off=6, blur=9, alpha=0.38):
    pad = blur*3*SS
    bx0, by0 = int(x0*SS - pad), int(y0*SS - pad + off*SS)
    bx1, by1 = int(x1*SS + pad), int(y1*SS + pad + off*SS)
    m = Image.new("L", (bx1-bx0, by1-by0), 0)
    ImageDraw.Draw(m).rounded_rectangle([pad, pad, pad+(x1-x0)*SS, pad+(y1-y0)*SS], radius=r*SS, fill=int(255*alpha))
    dr._im.paste((0, 0, 0), (bx0, by0), m.filter(ImageFilter.GaussianBlur(blur*SS)))

def board(dr, x0, y0, x1, y1, fill=INK, outline=None, r=26, seed=1, ow=3):
    """角丸の板(px は出力座標)。落ち影つき"""
    drop_shadow(dr, x0, y0, x1, y1, r)
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

TEXDIR = os.path.join(HERE, "textures")
_texc = {}
def load_tex(name):
    if name not in _texc:
        _texc[name] = Image.open(os.path.join(TEXDIR, name + "_diff_1k.jpg")).convert("RGB")
    return _texc[name]

def tile_to(img, w, h, scale):
    t = img.resize((max(2, int(img.width*scale)), max(2, int(img.height*scale))), Image.LANCZOS)
    out = Image.new("RGB", (w, h))
    for y in range(0, h, t.height):
        for x in range(0, w, t.width): out.paste(t, (x, y))
    return out, t.height

def paper_array():
    base, _ = tile_to(load_tex("concrete_wall_004"), CW, CH, 1.1)
    a = np.asarray(base, np.float32)
    a = a*0.28 + 255*0.72                                   # 明るくして濃い文字を読みやすく
    yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
    r2 = ((xx/CW-0.5)**2 + (yy/CH-0.5)**2)*2
    return a*(1 - 0.08*r2)[..., None]                        # わずかな周辺減光

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

FLOOR_W = 540
GX0, GX1 = CX - d/2*PPM + 14, CX + d/2*PPM - 14
_ST = {}
def stage_assets():
    if _ST: return _ST
    fl, th = tile_to(load_tex("painted_metal_shutter"), FLOOR_W, (BOT-TOP)*SS + 800, 0.62)
    fa = np.asarray(fl, np.float32); fa = fa*np.array([0.97, 1.0, 1.04], np.float32)
    _ST["floor"] = Image.fromarray(np.clip(fa, 0, 255).astype(np.uint8)); _ST["floor_th"] = th
    rw = 56
    rb, rth = tile_to(load_tex("rubber_tiles"), rw, (BOT-TOP)*SS + 600, 0.30)
    u = (np.arange(rw) + 0.5)/rw
    shade = 0.35 + 1.05*np.sin(np.pi*np.clip(u*0.92 + 0.02, 0, 1))**1.4    # 丸い断面(中央が明るい)
    ra = np.asarray(rb, np.float32)*2.4*shade[None, :, None]*np.array([0.9, 0.97, 1.12], np.float32)
    _ST["rail"] = Image.fromarray(np.clip(ra, 0, 255).astype(np.uint8)); _ST["rail_th"] = rth
    # 影(手すりのきわ・上下の光の落ち)
    yy, xx = np.mgrid[0:CH, 0:CW].astype(np.float32)
    al = np.zeros((CH, CW), np.float32)
    for side in (-1, 1):
        edge = (CX + side*(d/2*PPM + 14))*SS
        dist = np.where(side*(xx - edge) > 0, side*(xx - edge), 1e9)
        al = np.maximum(al, 0.55*np.exp(-dist/(16*SS)))
    vy = np.clip((yy/SS - TOP)/(BOT - TOP), 0, 1)
    al = np.maximum(al, 0.22*(1 - np.sin(np.pi*vy)))
    _ST["ao"] = Image.fromarray((np.clip(al, 0, 1)*255).astype(np.uint8))
    return _ST

_STAGE = None
def stage_base():
    """背景の壁 + すき間(深い影の穴)。床・手すりは毎フレーム流れる"""
    global _STAGE
    if _STAGE is not None: return _STAGE
    a = np.asarray(paper(), np.float32).copy()
    x0, x1 = int(GX0*SS), int(GX1*SS)
    pit, _ = tile_to(load_tex("worn_shutter"), x1-x0, (BOT-TOP)*SS, 0.7)
    pa = np.asarray(pit, np.float32)*0.22
    yy = np.linspace(0, 1, (BOT-TOP)*SS, dtype=np.float32)[:, None, None]
    xx = np.linspace(0, 1, x1-x0, dtype=np.float32)[None, :, None]
    pa = pa*(0.55 + 0.9*np.minimum(xx, 1-xx)*1.2 + 0.0*yy) + np.array([4, 3, 12], np.float32)   # 縁ほど暗い青みの影
    a[TOP*SS:BOT*SS, x0:x1] = pa
    _STAGE = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return _STAGE

def rail_paste(im, xr, top, bot, off, hw=14):
    st = stage_assets()
    h = int((bot - top)*SS)
    rail = st["rail"].crop((0, int(off) % st["rail_th"], 56, int(off) % st["rail_th"] + h))
    if hw != 14: rail = rail.resize((int(hw*2*SS), h), Image.BICUBIC)
    m = Image.new("L", rail.size, 255)
    im.paste(rail, (int(xr*SS - rail.width/2), int(top*SS)), m)

def rail_shape(dr, xr, top, bot, hw, seed):
    """why シーン用の静止した手すり(実写ゴム)"""
    drop_shadow(dr, xr-hw, top, xr+hw, bot, 8, off=4, blur=6, alpha=0.4)
    rail_paste(dr._im, xr, top, bot, 0, hw)

def stage_canvas():
    im = stage_base().copy()
    dr = ImageDraw.Draw(im); dr._im = im
    return im, dr

def decal(im, pts, color, alpha, blur=0.7):
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    pad = 6*SS
    bx0, by0, bx1, by1 = int(min(xs)-pad), int(min(ys)-pad), int(max(xs)+pad), int(max(ys)+pad)
    m = Image.new("L", (bx1-bx0, by1-by0), 0); md = ImageDraw.Draw(m)
    q = [(x-bx0, y-by0) for x, y in pts]
    md.polygon(q, fill=255); md.line(q + [q[0], q[1]], fill=255, width=4*SS, joint="curve")
    m = m.filter(ImageFilter.GaussianBlur(blur*SS)).point(lambda v: int(v*alpha))
    im.paste(color, (bx0, by0), m)

def draw_stage_dyn(dr, ts):
    """動く部分: 床(流れる金属板)・矢印の塗装・手すり(黒ゴム)・黄色い目印。向きは手すりの動き(物理)と一致させる"""
    im = dr._im
    st = stage_assets()
    for side, sgn in ((-1, -1), (1, 1)):
        off = (sgn*v*ts*PPM*SS) % st["floor_th"]
        h = (BOT-TOP)*SS
        crop = st["floor"].crop((0, int(off), FLOOR_W, int(off) + h))
        fx = (CX + side*(d/2*PPM + 14))*SS
        px = int(fx) if side > 0 else int(fx - FLOOR_W)
        im.paste(crop, (px, TOP*SS))
    im.paste((0, 0, 0), (0, 0), st["ao"])
    for side, sgn in ((-1, -1), (1, 1)):
        ax = CX + side*(d/2*PPM + 110)
        for k in range(4):
            yy = TOP + ((k*240 - sgn*v*ts*PPM) % 960)
            tip = -sgn*26
            if yy - 30 < TOP+6 or yy + 30 > BOT-6: continue
            tri = [(ax*SS, (yy+tip)*SS), ((ax-18)*SS, (yy-tip*0.2)*SS), ((ax+18)*SS, (yy-tip*0.2)*SS)]
            decal(im, tri, (236, 232, 214), 0.78)       # かすれた塗装の矢印
    for side, sgn in ((-1, -1), (1, 1)):
        xr = CX + side*d/2*PPM
        off = (sgn*v*ts*PPM*SS) % st["rail_th"]
        rail_paste(im, xr, TOP, BOT, off)
        per = 40
        y = TOP - per + ((-sgn*v*ts*PPM) % per)       # 手すりと同じ向きに動く目印
        while y < BOT:
            if TOP+10 < y < BOT-10:
                r = 5*SS
                dr.ellipse([xr*SS-r, y*SS-r, xr*SS+r, y*SS+r], fill=(236, 186, 48), outline=(120, 90, 20), width=2)
            y += per

# ---------- キリン(擬人化・仰向け・セル画調) ----------
def draw_cel_giraffe(K):
    """真上から見て、仰向けに寝た人間と同じ姿勢の直立二足歩行キリン。頭が+x。足先(-0.85)〜鼻先(+0.85)=1.70m"""
    R3 = int(0.95*K) + 12
    im = Image.new("RGBA", (2*R3, 2*R3), (0, 0, 0, 0)); dr = ImageDraw.Draw(im)
    lw = max(2, int(0.011*K))
    SKIN, SPOT, BELLY, HOOF = (255, 205, 95), (196, 122, 52), (255, 238, 196), (96, 68, 58)
    P = lambda x, y: (R3 + x*K, R3 - y*K)
    def rr(x0, y0, x1, y1, r, fill, ow=True):
        dr.rounded_rectangle([*P(x0, y1), *P(x1, y0)], radius=r*K, fill=fill, outline=INK if ow else None, width=lw)
    def el(cx, cy, rx, ry, fill, ow=True):
        dr.ellipse([*P(cx-rx, cy+ry), *P(cx+rx, cy-ry)], fill=fill, outline=INK if ow else None, width=lw)
    for sy in (-1, 1):                                   # 脚(そろえて足先は-側)
        rr(-0.85, sy*0.058-0.046, -0.16, sy*0.058+0.046, 0.046, SKIN)
        rr(-0.85, sy*0.058-0.046, -0.77, sy*0.058+0.046, 0.04, HOOF)
        for x in (-0.62, -0.42, -0.27): el(x, sy*0.058, 0.026, 0.024, SPOT, False)
    rr(0.18, -0.07, 0.64, 0.07, 0.07, SKIN)              # 首
    for x, y in ((0.30, 0.02), (0.43, -0.025), (0.55, 0.02)): el(x, y, 0.024, 0.02, SPOT, False)
    rr(-0.22, -0.15, 0.28, 0.15, 0.10, BELLY)            # 胴(おなか側が上)
    for x, y in ((-0.10, 0.06), (0.04, -0.07), (0.16, 0.07)): el(x, y, 0.034, 0.03, SPOT, False)
    for sy in (-1, 1):                                   # 腕(体の横にそろえる)
        rr(-0.14, sy*0.185-0.04, 0.27, sy*0.185+0.04, 0.04, SKIN)
        rr(-0.14, sy*0.185-0.04, -0.07, sy*0.185+0.04, 0.035, HOOF)
        for x in (0.02, 0.13, 0.22): el(x, sy*0.185, 0.02, 0.018, SPOT, False)
    for sy in (-1, 1):                                   # 耳・つの
        el(0.60, sy*0.135, 0.05, 0.026, SKIN)
        rr(0.575, min(sy*0.07, sy*0.105), 0.595, max(sy*0.07, sy*0.105), 0.008, SKIN)
        el(0.585, sy*0.115, 0.022, 0.022, HOOF)
    el(0.68, 0, 0.17, 0.105, SKIN)                       # 頭
    el(0.79, 0, 0.07, 0.07, (255, 224, 164))             # 鼻先
    for sy in (-1, 1):
        el(0.845, sy*0.026, 0.008, 0.008, HOOF, False)   # 鼻の穴
        el(0.71, sy*0.058, 0.019, 0.024, INK, False)     # 目
        el(0.716, sy*0.065, 0.007, 0.008, (255, 255, 255), False)
        el(0.66, sy*0.075, 0.02, 0.014, (255, 172, 160), False)  # ほお
    return im, R3

class Giraffe:
    placeholder = False
    def __init__(self):
        R = int(0.95*PPM*SS) + 12
        big, R3 = draw_cel_giraffe(PPM*SS*3)
        self.R = R
        self.sq = big.convert("RGBa").resize((2*R, 2*R), Image.LANCZOS)
        self.shadow = self.sq.convert("RGBA").split()[3].filter(ImageFilter.GaussianBlur(6*SS)).point(lambda q: int(q*0.5))   # ベタの影(最小限)

    def draw(self, dr, xc, yc, th, scale=1.0, k=0.0):
        im = dr._im
        px, py = w2s(xc, yc)
        deg = math.degrees(th)
        def prep(src):
            s2 = src
            if scale != 1.0:
                n = max(2, round(src.width*scale)); s2 = src.resize((n, n), Image.BICUBIC)
            return s2.rotate(deg, resample=Image.BICUBIC)
        rs = prep(self.shadow)
        ox, oy = 7*SS*scale, 11*SS*scale
        im.paste((10, 10, 16), (int(px - rs.width/2 + ox), int(py - rs.height/2 + oy)), rs)
        rg = prep(self.sq).convert("RGBA")
        rgb, a = rg.convert("RGB"), rg.split()[3]
        if k > 0:
            rgb = Image.blend(rgb, Image.new("RGB", rgb.size, (130, 130, 140)), 0.8*k)   # 灰色っぽく
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
        marker_band(dr, W/2, 860, 708, 100, seed=2)
        text(dr, (W/2, 740), "一生", sz, fill=SHU)
        text(dr, (W/2, 860), "くるくる回るのか？", sz, fill=SHU)
    return im

# ---------- 3D(three.js)で描いた画に、HUD・文字を重ねる ----------
CUR = {"key": None}
FRAMES3D = os.path.join(HERE, "frames3d")
SCENES3D = ("setup", "realtime", "slowmo", "why", "demo")
def base3d():
    key = CUR["key"]
    im = Image.open(os.path.join(FRAMES3D, key + ".jpg")).convert("RGB").resize((CW, CH), Image.LANCZOS)
    meta = json.load(open(os.path.join(FRAMES3D, key + ".json")))
    dr = ImageDraw.Draw(im); dr._im = im
    return im, dr, meta

def hud(dr, ts, slow_label=None):
    """経過時間・回転した角度のパネル(数値・項目名・位置・サイズは元のまま)"""
    st = state(min(ts, T_FALL))
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

def run_node(items, workers=4):
    import json as _j
    os.makedirs(FRAMES3D, exist_ok=True)
    todo = [it for it in items if not (os.path.exists(os.path.join(FRAMES3D, it["key"] + ".jpg")) and os.path.exists(os.path.join(FRAMES3D, it["key"] + ".json")))]
    print("3D frames to render:", len(todo), "of", len(items), flush=True)
    if not todo: return
    procs = []
    for w in range(workers):
        part = todo[w::workers]
        if not part: continue
        jf = os.path.join(FRAMES3D, f"_items{w}.json"); _j.dump(part, open(jf, "w"))
        procs.append(subprocess.Popen(["node", os.path.join(HERE, "web3d", "render_frames.js"), jf, FRAMES3D], cwd=os.path.join(HERE, "web3d")))
    for p in procs: p.wait()

@scene(7.0)
def setup(t):
    im, dr, meta = base3d()
    lx, ly = meta["label"]
    board(dr, lx-80, ly-28, lx+80, ly+28, fill=PAPER, outline=INK, r=16, seed=62)
    text(dr, (lx, ly), "50cm", 40, fill=SHU)
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
    im, dr, _ = base3d()
    hud(dr, t, slow_label="実際の速さ")
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
    im, dr, _ = base3d()
    ts = t/SLOW if t < T_FALL*SLOW else T_FALL + (t - T_FALL*SLOW)
    hud(dr, ts, slow_label="スロー 1/8倍速")
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
    im, dr, _ = base3d()
    board(dr, 14, 10, W-14, 112, seed=91)
    text(dr, (W/2, 60), "なぜ一生は回れないのか", 46, fill=LIGHT)
    items = [(0, "50cm", BLU), (45, "71cm", PUR), (72.9, "170cm", RED)]
    for i, (deg, lab, col) in enumerate(items):
        a = ease((t - 0.4 - i*1.4)/0.5)
        if a <= 0: continue
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


disc_th = np.load(os.path.join(HERE, "disc_traj.npy"))

@scene(3.5)
def demo_card(t):
    im, dr = canvas()
    a, b, c = ease(t/0.5), ease((t-0.9)/0.5), ease((t-1.8)/0.5)
    text(dr, (W/2, 330), "実現例", 44, fill=SHU, alpha=a)
    text(dr, (W/2, 470), "寝転ぶ体を", 58, fill=INK, alpha=a)
    text(dr, (W/2, 560), "丸い台にのせたら…", 58, fill=INK, alpha=b)
    if t > 1.8:
        marker_band(dr, W/2, 740, 640, 100, seed=7)
        text(dr, (W/2, 740), "ずっと回れる！", int(76 + 30*(1-c)), fill=SHU)
    return im

@scene(12.0)
def demo(t):
    im, dr, _ = base3d()
    i = min(int(round(t/1e-3)), len(disc_th)-1); ang = math.degrees(disc_th[i])
    board(dr, 14, 10, W-14, 112, seed=151)
    text(dr, (W/2, 60), "実現例：丸い台", 44, fill=LIGHT)
    board(dr, 24, 1092, 356, 1262, seed=152)
    board(dr, 364, 1092, 696, 1262, seed=153)
    text(dr, (190, 1150), "経過時間", 30, fill=LIGHT2, black=False)
    text(dr, (190, 1215), f"{t:4.2f} 秒", 62, fill=LIGHT)
    text(dr, (530, 1150), "回転した角度", 30, fill=LIGHT2, black=False)
    text(dr, (530, 1215), f"{ang:5.1f}°", 62, fill=YAMA)
    cap = None
    if 0.5 < t < 4.0: cap = "丸い台は どの角度でも手すりにのる"
    elif 4.0 < t < 8.5: cap = "左右で逆向き → 回り続ける"
    elif t > 8.5: cap = "落ちない！ ずっとくるくる回れる"
    if cap:
        board(dr, 14, 126, W-14, 202, fill=PAPER, outline=INK, r=22, seed=161)
        text(dr, (W/2, 164), cap, 36, fill=INK)
    if t > 9.5:
        k = ease((t-9.5)/0.3)
        board(dr, W/2-250, 520, W/2+250, 680, fill=BLUE_OK, outline=INK, r=30, seed=171)
        text(dr, (W/2, 600), "ずっと回れた！", int(70+30*(1-k)), fill=(255, 255, 255))
    return im

@scene(3.5)
def caution(t):
    im, dr = canvas()
    a = ease(t/0.5)
    text(dr, (W/2, 580), "※とても危険です", 56, fill=SHU, alpha=a)
    text(dr, (W/2, 670), "絶対にまねしないでください", 50, fill=INK, alpha=a)
    text(dr, (W/2, 820), "体を1本の棒とみなした物理シミュレーションです", 26, fill=(86, 70, 60), black=False, alpha=a)
    return im

# 文字カードも止め絵にせず、ゆっくり寄りながら流れる(ドローン風)
def kenburns(im, u, dx, dy):
    sc = 1.0 + 0.08*u
    w, h = CW/sc, CH/sc
    x0 = (CW-w)*(0.5 + 0.4*dx*(u-0.5)); y0 = (CH-h)*(0.5 + 0.4*dy*(0.5-u))
    return im.crop((int(x0), int(y0), int(x0+w), int(y0+h))).resize((CW, CH), Image.BICUBIC)
def _wrap(fn, dur, dx, dy):
    def w(t): return kenburns(fn(t), t/dur, dx, dy)
    w.__name__ = fn.__name__; return w
_kb = {"demo_card": (1, -1), "title": (1, 1), "countdown": (-1, 1), "slowcard": (1, -1), "result": (-1, -1), "caution": (1, 1)}
for _i, (_dur, _fn) in enumerate(scenes):
    if _fn.__name__ in _kb: scenes[_i] = (_dur, _wrap(_fn, _dur, *_kb[_fn.__name__]))

# ---------- コントラスト確認 ----------
def _lum(c):
    f = lambda u: (u/255/12.92) if u/255 <= 0.03928 else (((u/255)+0.055)/1.055)**2.4
    r, g, b = c; return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b)
def contrast(a, b):
    la, lb = sorted((_lum(a), _lum(b)), reverse=True); return (la+0.05)/(lb+0.05)
CHECKS = [
    ("パネル上: 時間/文言", LIGHT, INK, 4.5), ("パネル上: 項目名", LIGHT2, INK, 4.5), ("パネル上: 角度(山吹)", YAMA, INK, 4.5),
    ("紙上: 本文", INK, PAPER, 4.5), ("紙上: 朱色(大文字)", SHU, PAPER, 3.0), ("帯上: 朱色(大文字)", SHU, (250, 218, 120), 3.0),
    ("紙上: ○", BLUE_OK, PAPER, 3.0), ("紙上: 注意書き小文字", (86, 70, 60), PAPER, 4.5),
    ("落下！(白/朱)", (255, 255, 255), SHU, 3.0), ("why 0°ラベル(白/青)", (255, 255, 255), BLU, 3.0),
    ("why 45°ラベル(白/紫)", (255, 255, 255), PUR, 3.0), ("why 73°ラベル(白/赤)", (255, 255, 255), RED, 3.0),
    ("50cm(朱/紙箱)", SHU, PAPER, 3.0),
]
def run_check():
    bad = 0
    for n, f, b, need in CHECKS:
        c = contrast(f, b); ok = c >= need; bad += (not ok)
        print(f"{'OK ' if ok else 'NG '} {c:5.2f} (>= {need})  {n}")
    a = np.asarray(paper().resize((360, 640)), np.float32).reshape(-1, 3)
    lum = a @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    dark = tuple(int(x) for x in a[np.argsort(lum)[int(len(lum)*0.05)]])
    for n, f, need in (("実背景(暗い所5%)上: 本文", INK, 4.5), ("実背景(暗い所5%)上: 朱色(大文字)", SHU, 3.0), ("実背景(暗い所5%)上: ○", BLUE_OK, 3.0), ("実背景(暗い所5%)上: 小さい注意書き", (86, 70, 60), 4.5)):
        c = contrast(f, dark); ok = c >= need; bad += (not ok)
        print(f"{'OK ' if ok else 'NG '} {c:5.2f} (>= {need})  {n} bg={dark}")
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
    tone(S["demo"]+9.5, 1046, 0.7, 0.35, 4); tone(S["demo"]+9.58, 1318, 0.7, 0.3, 4); tone(S["demo"]+9.66, 1568, 0.9, 0.3, 3)
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

_VIG = None
_RNG = np.random.default_rng(11)
def finish(im):
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        _VIG = (1 - 0.16*(((xx/W-0.5)**2 + (yy/H-0.5)**2)*2))[..., None]
    a = np.asarray(im, np.float32)*_VIG + _RNG.normal(0, 2.4, (H, W, 1)).astype(np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

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
        items = [{"key": f"pv_{n}_{tl:.2f}", "scene": n, "t": tl, "T": float(S[n] + tl)} for n, tl in shots if n in SCENES3D]
        run_node(items, workers=2)
        for name, tl in shots:
            CUR["key"] = f"pv_{name}_{tl:.2f}"
            finish(fns[name](tl).resize((W, H), Image.LANCZOS)).save(os.path.join(HERE, f"pv_3_{name}_{tl:.2f}.png"))
        sys.exit()
    nfr = int(TOTAL*FPS)
    items, idx = [], 0
    for f in range(nfr):
        t = f/FPS
        while idx < len(scenes)-1 and t >= starts[idx+1]: idx += 1
        n = scenes[idx][1].__name__
        if n in SCENES3D: items.append({"key": f"f{f:05d}", "scene": n, "t": float(t - starts[idx]), "T": float(t)})
    run_node(items, workers=4)
    audio, has_voice = build_audio()
    with wave.open(os.path.join(HERE, "audio_3d_full.wav"), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((audio*32000).astype(np.int16).tobytes())
    af = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"] if has_voice else []
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", os.path.join(HERE, "audio_3d_full.wav"),
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                          *af, "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                          os.path.join(HERE, "dosoku_kaiten_3d_full.mp4")], stdin=subprocess.PIPE)
    idx = 0
    for f in range(nfr):
        t = f/FPS
        while idx < len(scenes)-1 and t >= starts[idx+1]: idx += 1
        CUR["key"] = f"f{f:05d}"
        im = finish(scenes[idx][1](t - starts[idx]).resize((W, H), Image.LANCZOS))
        p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()
    print("total", TOTAL, "frames", nfr, "voice", has_voice)
