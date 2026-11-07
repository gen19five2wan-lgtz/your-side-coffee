s = open("render_real.py").read()
def cut(s, a, b, new):
    i, j = s.index(a), s.index(b)
    return s[:i] + new + s[j:]
s = s.replace("pv_r_", "pv_3_").replace("dosoku_kaiten_real.mp4", "dosoku_kaiten_3d.mp4").replace("audio_real.wav", "audio_3d.wav")

helpers = '''# ---------- 3D(three.js)で描いた画に、HUD・文字を重ねる ----------
CUR = {"key": None}
FRAMES3D = os.path.join(HERE, "frames3d")
SCENES3D = ("setup", "realtime", "slowmo", "why")
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

'''
s = cut(s, "@scene(7.0)\ndef setup", "@scene(4.0)\ndef countdown", helpers)

s = cut(s, "REAL_HOLD = 3.0", "@scene(2.5)\ndef slowcard", '''REAL_HOLD = 3.0
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

''')

s = cut(s, "SLOW = 8.0", "@scene(6.0)\ndef result", '''SLOW = 8.0
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

''')

s = s.replace("# ---------- コントラスト確認 ----------", '''# 文字カードも止め絵にせず、ゆっくり寄りながら流れる(ドローン風)
def kenburns(im, u, dx, dy):
    sc = 1.0 + 0.08*u
    w, h = CW/sc, CH/sc
    x0 = (CW-w)*(0.5 + 0.4*dx*(u-0.5)); y0 = (CH-h)*(0.5 + 0.4*dy*(0.5-u))
    return im.crop((int(x0), int(y0), int(x0+w), int(y0+h))).resize((CW, CH), Image.BICUBIC)
def _wrap(fn, dur, dx, dy):
    def w(t): return kenburns(fn(t), t/dur, dx, dy)
    w.__name__ = fn.__name__; return w
_kb = {"title": (1, 1), "countdown": (-1, 1), "slowcard": (1, -1), "result": (-1, -1), "caution": (1, 1)}
for _i, (_dur, _fn) in enumerate(scenes):
    if _fn.__name__ in _kb: scenes[_i] = (_dur, _wrap(_fn, _dur, *_kb[_fn.__name__]))

# ---------- コントラスト確認 ----------''', 1)

s = cut(s, '    if arg == "preview":', 'XXXX_END', '') if False else s
i = s.index('    if arg == "preview":')
s = s[:i] + '''    if arg == "preview":
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
    with wave.open(os.path.join(HERE, "audio_3d.wav"), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
        wf.writeframes((audio*32000).astype(np.int16).tobytes())
    af = ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"] if has_voice else []
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                          "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-i", os.path.join(HERE, "audio_3d.wav"),
                          "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
                          *af, "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart",
                          os.path.join(HERE, "dosoku_kaiten_3d.mp4")], stdin=subprocess.PIPE)
    idx = 0
    for f in range(nfr):
        t = f/FPS
        while idx < len(scenes)-1 and t >= starts[idx+1]: idx += 1
        CUR["key"] = f"f{f:05d}"
        im = finish(scenes[idx][1](t - starts[idx]).resize((W, H), Image.LANCZOS))
        p.stdin.write(im.tobytes())
    p.stdin.close(); p.wait()
    print("total", TOTAL, "frames", nfr, "voice", has_voice)
'''
open("render_3d.py", "w").write(s)
