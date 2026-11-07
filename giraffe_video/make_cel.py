import re
s = open("render_giraffe.py").read()
def cut(s, a, b, new):
    i, j = s.index(a), s.index(b)
    return s[:i] + new + s[j:]

# palette
s = s.replace("PAPER = (250, 243, 226)", "PAPER = (255, 246, 226)")
s = s.replace("SHU = (200, 55, 35)", "SHU = (214, 60, 38)")
s = s.replace("YAMA = (244, 190, 60)", "YAMA = (255, 200, 60)")
s = s.replace("NAVY = (34, 46, 102)", "NAVY = (52, 88, 190)").replace("NAVY_HI = (62, 80, 148)", "NAVY_HI = (130, 168, 240)")
s = s.replace("GAPC = (66, 52, 104)", "GAPC = (92, 84, 150)")
# 主線は揺らさない(均一)
s = s.replace("    rng = np.random.default_rng(seed)\n    out = []\n    for (x0, y0)", "    rng = np.random.default_rng(seed); j = 0\n    out = []\n    for (x0, y0)")
s = s.replace("2.4*math.sin", "0*math.sin")
s = s.replace("(176, 206, 176)", "(196, 226, 196)").replace("(172, 210, 178)", "(150, 210, 170)")
s = s.replace("pv_g_", "pv_c_").replace("dosoku_kaiten_giraffe.mp4", "dosoku_kaiten_cel.mp4").replace("audio_giraffe.wav", "audio_cel.wav")

s = cut(s, "def paper_array():", "_PAPER = None", '''def paper_array():
    return np.ones((CH, CW, 3), np.float32)*np.array(PAPER, np.float32)

''')
s = cut(s, "def stage_base():", "def stage_canvas():", '''def stage_base():
    """ベタ塗りの舞台: 床・すき間・手すり。影は最小限(すき間の縁だけ)"""
    global _STAGE
    if _STAGE is not None: return _STAGE
    im = paper().copy(); dr = ImageDraw.Draw(im)
    gx0, gx1 = CX - d/2*PPM + 14, CX + d/2*PPM - 14
    for x0, x1 in ((-4, gx0 - 14), (gx1 + 14, W+4)):
        dr.rectangle([x0*SS, TOP*SS, x1*SS, BOT*SS], fill=(230, 243, 214), outline=INK, width=3*SS)
    dr.rectangle([gx0*SS, TOP*SS, gx1*SS, BOT*SS], fill=GAPC)
    dr.rectangle([gx0*SS, TOP*SS, (gx0+16)*SS, BOT*SS], fill=(70, 62, 124))   # 縁の影
    for k, side in enumerate((-1, 1)):
        rail_shape(dr, CX + side*d/2*PPM, TOP, BOT, 14, 30+k)
    _STAGE = im
    return im

''')

giraffe_code = '''# ---------- キリン(擬人化・仰向け・セル画調) ----------
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
        self.shadow = self.sq.convert("RGBA").split()[3].point(lambda q: int(q*0.22))   # ベタの影(最小限)

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
        ox, oy = 5*SS*scale, 8*SS*scale
        im.paste((60, 50, 80), (int(px - rs.width/2 + ox), int(py - rs.height/2 + oy)), rs)
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

'''
s = cut(s, "# ---------- キリン ----------", "def arrow(", giraffe_code)
open("render_cel.py", "w").write(s)
