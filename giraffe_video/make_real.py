s = open("render_cel.py").read()
def cut(s, a, b, new):
    i, j = s.index(a), s.index(b)
    return s[:i] + new + s[j:]

s = s.replace("SHU = (214, 60, 38)", "SHU = (192, 46, 28)").replace("(110, 90, 78)", "(86, 70, 60)")
s = s.replace("pv_c_", "pv_r_").replace("dosoku_kaiten_cel.mp4", "dosoku_kaiten_real.mp4").replace("audio_cel.wav", "audio_real.wav")

# ---- 背景(文字カード用): 実写コンクリートブロック壁を明るく ----
s = cut(s, "def paper_array():", "def canvas():", '''TEXDIR = os.path.join(HERE, "textures")
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

''')

# ---- 板の落ち影 ----
s = cut(s, "def board(", "def text(", '''def drop_shadow(dr, x0, y0, x1, y1, r, off=6, blur=9, alpha=0.38):
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

''')

# ---- 舞台: 実写テクスチャの床(溝つき金属板)・黒ゴムの手すり・深いすき間 ----
s = cut(s, "def rail_shape(", "def stage_canvas():", '''FLOOR_W = 540
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

''')

s = cut(s, "def draw_stage_dyn(", "# ---------- キリン", '''def decal(im, pts, color, alpha, blur=0.7):
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

''')

# ---- キリンの影をやわらかく(接地) ----
s = s.replace("self.shadow = self.sq.convert(\"RGBA\").split()[3].point(lambda q: int(q*0.22))",
              "self.shadow = self.sq.convert(\"RGBA\").split()[3].filter(ImageFilter.GaussianBlur(6*SS)).point(lambda q: int(q*0.5))")
s = s.replace("ox, oy = 5*SS*scale, 8*SS*scale", "ox, oy = 7*SS*scale, 11*SS*scale")
s = s.replace("im.paste((60, 50, 80), (int(px - rs.width/2 + ox)", "im.paste((10, 10, 16), (int(px - rs.width/2 + ox)")

# ---- 仕上げ: 周辺減光 + フィルムグレイン ----
s = s.replace("# ---------- main ----------", '''_VIG = None
_RNG = np.random.default_rng(11)
def finish(im):
    global _VIG
    if _VIG is None:
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        _VIG = (1 - 0.16*(((xx/W-0.5)**2 + (yy/H-0.5)**2)*2))[..., None]
    a = np.asarray(im, np.float32)*_VIG + _RNG.normal(0, 2.4, (H, W, 1)).astype(np.float32)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

# ---------- main ----------''')
s = s.replace("fns[name](tl).resize((W, H), Image.LANCZOS).save(", "finish(fns[name](tl).resize((W, H), Image.LANCZOS)).save(")
s = s.replace("im = scenes[idx][1](t - starts[idx]).resize((W, H), Image.LANCZOS)", "im = finish(scenes[idx][1](t - starts[idx]).resize((W, H), Image.LANCZOS))")

# ---- コントラスト: 実際の背景の暗い所(下位5%)でも確認 ----
s = s.replace("    return bad\\n", "")
s = s.replace("def run_check():\\n    bad = 0\\n", "def run_check():\\n    bad = 0\\n")
open("render_real.py", "w").write(s)
