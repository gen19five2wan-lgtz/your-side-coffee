// 動く歩道 × 仰向けの擬人化キリン(3D)。物理は sim.py の軌道(traj.json)をそのまま使う。
// world: X=x(右), Y=上, Z=-y(物理のy+が画面奥=北)
const PPM = 330, D = 0.5, V = 0.67, LEN = 1.70;
const RAIL_HW = 14 / PPM;
const RAIL_TOP = 0.95, BODY_Y = RAIL_TOP + 0.11;   // 手すりの高さ: 床から約95cm
const PANEL_IN = 0.28, BELT_IN = 0.40, BELT_W = 1.0, TUN_R = 3.3, TUN_Y0 = 0.9;
const W = 720, H = 1280;
let TRAJ, DISC, TF, renderer, scene3, camera, G = {};
const ease = x => { x = Math.min(Math.max(x, 0), 1); return x * x * (3 - 2 * x); };
const state = ts => TRAJ[Math.min(Math.round(ts / 1e-4), TRAJ.length - 1)];
const mod = (a, n) => ((a % n) + n) % n;

function loadTex(name, repeat, srgb = true) {
  return new Promise(res => new THREE.TextureLoader().load(`/textures/${name}_diff_1k.jpg`, t => {
    t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(repeat[0], repeat[1]);
    t.anisotropy = renderer.capabilities.getMaxAnisotropy();
    if (srgb) t.colorSpace = THREE.SRGBColorSpace; res(t);
  }));
}

function spotsTexture(base, spot, line, seed) {
  const c = document.createElement('canvas'); c.width = c.height = 512; const g = c.getContext('2d');
  let s = seed; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  g.fillStyle = base; g.fillRect(0, 0, 512, 512);
  g.lineJoin = 'round'; g.strokeStyle = line; g.fillStyle = spot; g.lineWidth = 7;
  for (let i = 0; i < 70; i++) {                       // 網目模様(あみめ): 茶色のパッチ+クリームの境界
    const cx = rnd() * 512, cy = rnd() * 512, r = 26 + rnd() * 34, n = 7;
    for (const [ox, oy] of [[0, 0], [-512, 0], [512, 0], [0, -512], [0, 512]]) {
      g.beginPath();
      for (let k = 0; k < n; k++) {
        const a = k / n * Math.PI * 2, rr = r * (0.75 + 0.35 * ((Math.sin(k * 7 + i) + 1) / 2));
        const x = cx + ox + Math.cos(a) * rr, y = cy + oy + Math.sin(a) * rr;
        k ? g.lineTo(x, y) : g.moveTo(x, y);
      }
      g.closePath(); g.fill(); g.stroke();
    }
  }
  const t = new THREE.CanvasTexture(c); t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = 8; return t;
}


function cityTexture() {
  const c = document.createElement('canvas'); c.width = 2048; c.height = 512; const g = c.getContext('2d');
  let sd = 4242; const rnd = () => (sd = (sd * 16807) % 2147483647) / 2147483647;
  const gr = g.createLinearGradient(0, 0, 0, 512); gr.addColorStop(0, '#04060c'); gr.addColorStop(0.55, '#0a1020'); gr.addColorStop(1, '#1a1620');
  g.fillStyle = gr; g.fillRect(0, 0, 2048, 512);
  for (let x = 0; x < 2048;) {                                  // ビルのシルエットと窓あかり
    const w = 40 + rnd() * 110, h = 120 + rnd() * 300; g.fillStyle = `rgb(${10 + rnd() * 14},${12 + rnd() * 14},${20 + rnd() * 18})`; g.fillRect(x, 512 - h, w, h);
    for (let wy = 512 - h + 10; wy < 500; wy += 14) for (let wx = x + 6; wx < x + w - 8; wx += 12) if (rnd() < 0.28) { g.fillStyle = rnd() < 0.8 ? 'rgba(255,214,140,0.85)' : 'rgba(190,225,255,0.85)'; g.fillRect(wx, wy, 5, 7); }
    x += w + rnd() * 14;
  }
  for (let i = 0; i < 160; i++) {                               // ボケた街あかり
    const x = rnd() * 2048, y = 150 + rnd() * 330, r = 6 + rnd() * 20, k = rnd();
    const col = k < 0.45 ? '255,236,200' : k < 0.7 ? '255,120,90' : k < 0.88 ? '150,210,255' : '255,190,90';
    const rg = g.createRadialGradient(x, y, 0, x, y, r); rg.addColorStop(0, `rgba(${col},0.45)`); rg.addColorStop(1, `rgba(${col},0)`); g.fillStyle = rg; g.fillRect(x - r, y - r, 2 * r, 2 * r);
  }
  const t = new THREE.CanvasTexture(c); t.wrapS = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace; return t;
}

function buildGiraffe() {
  const grp = new THREE.Group();
  const skinTex = spotsTexture('#e0b46a', '#8a5026', '#f3dfae', 12345);
  const bellyTex = spotsTexture('#f3e2bd', '#c98c4c', '#f7ecd0', 777);
  const skin = new THREE.MeshStandardMaterial({ map: skinTex, roughness: 0.9 });
  const belly = new THREE.MeshStandardMaterial({ map: bellyTex, roughness: 0.9 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x3a2a24, roughness: 0.6 });
  const rosy = new THREE.MeshStandardMaterial({ color: 0xf0a8a0, roughness: 0.9 });
  const white = new THREE.MeshBasicMaterial({ color: 0xffffff });
  const fit = (mat, ru, rv) => { const m = mat.clone(); m.map = mat.map.clone(); m.map.needsUpdate = true; m.map.repeat.set(ru, rv); return m; };
  const capsule = (x0, x1, y, z, r, mat0) => {
    const mat = mat0.map ? fit(mat0, 2 * Math.PI * r / 0.5, ((x1 - x0)) / 0.5) : mat0;
    const geo = new THREE.CapsuleGeometry(r, Math.max(0.001, (x1 - x0) - 2 * r), 8, 20); geo.rotateZ(-Math.PI / 2);
    const m = new THREE.Mesh(geo, mat); m.position.set((x0 + x1) / 2, y, z); m.castShadow = m.receiveShadow = true; grp.add(m); return m;
  };
  const ell = (x, y, z, rx, ry, rz, mat0) => {
    const mat = mat0.map ? fit(mat0, 2 * Math.PI * Math.sqrt((ry * ry + rz * rz) / 2) / 0.5, 2 * rx / 0.5 * 0.9) : mat0;
    const sg = new THREE.SphereGeometry(1, 32, 20); sg.rotateZ(Math.PI / 2);
    const m = new THREE.Mesh(sg, mat); m.scale.set(rx, ry, rz); m.position.set(x, y, z);
    m.castShadow = m.receiveShadow = true; grp.add(m); return m;
  };
  for (const sz of [-1, 1]) {
    capsule(-0.85, -0.16, -0.055, sz * 0.058, 0.045, skin);                 // 脚
    ell(-0.82, -0.055, sz * 0.058, 0.055, 0.05, 0.05, dark);                // ひづめ
    capsule(-0.14, 0.27, -0.06, sz * 0.19, 0.04, skin);                     // 腕
    ell(-0.12, -0.06, sz * 0.19, 0.05, 0.043, 0.043, dark);
    ell(0.60, 0.0, sz * 0.14, 0.05, 0.012, 0.03, skin);                     // 耳
    const oss = capsule(0.57, 0.60, 0.0, sz * 0.095, 0.014, skin); oss.rotation.x = sz * 0.9;  // つの
    ell(0.585, -0.01, sz * 0.125, 0.022, 0.022, 0.022, dark);
  }
  capsule(0.18, 0.64, -0.035, 0, 0.065, skin);                              // 首
  ell(0.03, 0.0, 0, 0.28, 0.10, 0.15, belly);                               // 胴
  ell(0.68, -0.01, 0, 0.17, 0.09, 0.10, skin);                              // 頭
  ell(0.79, -0.015, 0, 0.075, 0.062, 0.07, belly);                          // 鼻先
  for (const sz of [-1, 1]) {
    ell(0.845, 0.012, sz * 0.026, 0.01, 0.008, 0.01, dark);                 // 鼻の穴
    ell(0.71, 0.072, sz * 0.058, 0.022, 0.02, 0.022, dark);                 // 目
    ell(0.716, (RAIL_TOP + 0.008), sz * 0.064, 0.007, 0.006, 0.007, white);
    ell(0.66, 0.07, sz * 0.078, 0.022, 0.012, 0.015, rosy);                 // ほお
  }
  grp.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  grp.traverse(o => {                                    // 真上からの平面投影UV(手足でも柄が伸びない)
    if (!o.isMesh || !o.material.map) return;
    o.updateMatrix(); const pos = o.geometry.attributes.position, uv = o.geometry.attributes.uv, v = new THREE.Vector3();
    for (let i = 0; i < pos.count; i++) { v.fromBufferAttribute(pos, i).applyMatrix4(o.matrix); uv.setXY(i, v.x / 0.55, v.z / 0.55); }
    uv.needsUpdate = true; o.material.map.repeat.set(1, 1);
  });
  return grp;
}

function buildPerson(seed, outerSign) {
  let sd = seed; const rnd = () => (sd = (sd * 16807) % 2147483647) / 2147483647, pick = a => a[Math.floor(rnd() * a.length)];
  const skin = pick([0xf1c9a5, 0xdfae88, 0xc08a62, 0x8d5a3c]), shirt = pick([0x2f4a7a, 0x7a2f2f, 0x2e6a4f, 0xcfc7b8, 0x3a3a42, 0xb8762e, 0x5a3e7a, 0x20242c]);
  const pants = pick([0x22252e, 0x3a3f52, 0x5a4a3a, 0x2a2a2a, 0x46506a]), hair = pick([0x1a1410, 0x3b2a1c, 0x6b5a40, 0x9a9a9a, 0x0e0e0e]);
  const mat = (c, r = 0.85) => new THREE.MeshStandardMaterial({ color: c, roughness: r });
  const M = { skin: mat(skin, 0.7), shirt: mat(shirt), pants: mat(pants), hair: mat(hair, 0.9), shoe: mat(0x15151a, 0.5) };
  const g = new THREE.Group();
  const part = (geo, m) => { const o = new THREE.Mesh(geo, m); o.castShadow = o.receiveShadow = true; return o; };
  const cap = (r, len, m, sz = 1) => { const o = part(new THREE.CapsuleGeometry(r, len, 6, 12), m); o.scale.z = sz; return o; };
  const limb = (x, y, upper, lower, r1, r2, m, mEnd, endGeo) => {          // 肩/股関節 → 上腕/太もも → ひじ/ひざ → 前腕/すね
    const j = new THREE.Group(); j.position.set(x, y, 0);
    const u = cap(r1, upper - 2 * r1, m); u.position.y = -upper / 2; j.add(u);
    const k = new THREE.Group(); k.position.y = -upper; j.add(k);
    const l = cap(r2, lower - 2 * r2, m); l.position.y = -lower / 2; k.add(l);
    if (endGeo) { const e = part(endGeo, mEnd); e.position.y = -lower - (endGeo.type === 'BoxGeometry' ? 0.02 : 0); e.position.z = endGeo.type === 'BoxGeometry' ? 0.06 : 0; k.add(e); }
    j.userData.knee = k; return j;
  };
  const legL = limb(-0.09, 0.93, 0.43, 0.45, 0.075, 0.055, M.pants, M.shoe, new THREE.BoxGeometry(0.1, 0.07, 0.27));
  const legR = limb(0.09, 0.93, 0.43, 0.45, 0.075, 0.055, M.pants, M.shoe, new THREE.BoxGeometry(0.1, 0.07, 0.27));
  g.add(legL, legR);
  const torso = cap(0.15, 0.30, M.shirt, 0.62); torso.position.y = 1.22; g.add(torso);                      // 胴(前後に薄い)
  const hip = part(new THREE.SphereGeometry(0.15, 16, 12), M.pants); hip.scale.set(1, 0.6, 0.62); hip.position.y = 0.97; g.add(hip);
  const neck = part(new THREE.CylinderGeometry(0.045, 0.05, 0.1, 10), M.skin); neck.position.y = 1.52; g.add(neck);
  const head = part(new THREE.SphereGeometry(0.105, 24, 18), M.skin); head.scale.set(0.92, 1.1, 1.0); head.position.y = 1.64; g.add(head);
  const hairM = part(new THREE.SphereGeometry(0.112, 24, 18, 0, Math.PI * 2, 0, Math.PI * 0.58), M.hair); hairM.scale.set(0.95, 1.1, 1.05); hairM.position.set(0, 1.655, -0.01); g.add(hairM);
  const armO = limb(outerSign * 0.2, 1.42, 0.28, 0.26, 0.05, 0.042, M.shirt, M.skin, new THREE.SphereGeometry(0.045, 10, 8));
  const armI = limb(-outerSign * 0.2, 1.42, 0.28, 0.26, 0.05, 0.042, M.shirt, M.skin, new THREE.SphereGeometry(0.045, 10, 8));
  armO.rotation.z = -outerSign * 0.62; armO.userData.knee.rotation.x = -0.35; armO.rotation.x = -0.25;               // 外側の手すりに手をのせる
  armI.rotation.z = outerSign * 0.06; armI.userData.knee.rotation.x = -0.5; armI.rotation.x = -0.1;
  g.add(armO, armI);
  if (rnd() < 0.5) { const bp = part(new THREE.BoxGeometry(0.3, 0.4, 0.16), mat(pick([0x2a2a30, 0x3a4a3a, 0x7a3a2a]), 0.9)); bp.position.set(0, 1.25, -0.17); g.add(bp); }   // リュック
  legL.userData.knee.rotation.x = 0.05; legR.userData.knee.rotation.x = 0.02;
  g.userData.sway = rnd() * 6.28; g.userData.head = head; g.userData.hair = hairM;
  return g;
}

async function init(aa = true) {
  renderer = new THREE.WebGLRenderer({ antialias: aa, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1.5); renderer.setSize(W, H);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  document.body.appendChild(renderer.domElement);
  DISC = await (await fetch('/web3d/disc_traj.json')).json(); TRAJ = await (await fetch('/web3d/traj.json')).json(); TF = TRAJ[TRAJ.length - 1][0];
  scene3 = new THREE.Scene(); scene3.background = new THREE.Color(0x05060b);
  camera = new THREE.PerspectiveCamera(72, W / H, 0.05, 120);
  scene3.add(new THREE.HemisphereLight(0xb8c4e0, 0x6a5e52, 1.15));
  const fill = new THREE.DirectionalLight(0xffecd0, 1.3); fill.position.set(1.5, 8, -1.0); scene3.add(fill);
  const sun = new THREE.DirectionalLight(0xffe2bc, 2.4); sun.position.set(-1.8, 6.5, 2.0); sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096); const sc = sun.shadow.camera; sc.left = -3.4; sc.right = 3.4; sc.top = 3.8; sc.bottom = -3.8; sc.near = 1; sc.far = 20;
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02; sun.shadow.radius = 5; scene3.add(sun);

  const [floorT, railT, deckT] = await Promise.all([
    loadTex('painted_metal_shutter', [BELT_W, 60]), loadTex('rubber_tiles', [1, 60 / 0.35]), loadTex('worn_shutter', [1, 30])]);
  G.floorTex = [floorT, floorT.clone()]; G.floorTex[1].needsUpdate = true;
  G.railTex = [railT, railT.clone()]; G.railTex[1].needsUpdate = true;
  const LZ = 60, add = m => { scene3.add(m); return m; };
  const whitePanel = new THREE.MeshStandardMaterial({ color: 0xf2f0ea, roughness: 0.28, metalness: 0.1, envMapIntensity: 1.3 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x1a1a1f, roughness: 0.4, metalness: 0.6 });
  const silver = new THREE.MeshStandardMaterial({ color: 0xc9ccd2, roughness: 0.22, metalness: 0.9 });
  const mkRail = (x, i) => {
    const rail = new THREE.Mesh(new THREE.CylinderGeometry(RAIL_HW, RAIL_HW, LZ, 28), new THREE.MeshStandardMaterial({ map: G.railTex[i], roughness: 0.22, metalness: 0.05, color: 0xffffff, envMapIntensity: 1.6 }));
    rail.geometry.rotateX(Math.PI / 2); rail.scale.y = 0.62; rail.position.set(x, RAIL_TOP - RAIL_HW * 0.62, 0); rail.castShadow = rail.receiveShadow = true; add(rail);
  };
  const box = (x, y, z, w, h, l, mat, shadow = true) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, l), mat); m.position.set(x, y, z); m.castShadow = shadow; m.receiveShadow = true; return add(m); };
  for (const [i, side] of [[0, -1], [1, 1]]) {
    const fl = new THREE.Mesh(new THREE.PlaneGeometry(BELT_W, LZ), new THREE.MeshStandardMaterial({ map: G.floorTex[i], roughness: 0.38, metalness: 0.4, color: 0xffffff, envMapIntensity: 1.6 }));
    fl.rotation.x = -Math.PI / 2; fl.position.set(side * (BELT_IN + BELT_W / 2), 0, 0); fl.receiveShadow = true; add(fl);
    mkRail(side * D / 2, i);                                                        // 内側の手すり(ここに寝転ぶ)
    mkRail(side * (BELT_IN + BELT_W + 0.10), i);                                    // 外側の手すり(同じ向きに動く)
    box(side * (PANEL_IN + 0.05), RAIL_TOP / 2 - 0.035, 0, 0.10, RAIL_TOP - 0.07, LZ, whitePanel);   // 内側パネル
    box(side * (BELT_IN + BELT_W + 0.10), RAIL_TOP / 2 - 0.035, 0, 0.10, RAIL_TOP - 0.07, LZ, whitePanel);
    box(side * (PANEL_IN + 0.05), 0.045, 0, 0.12, 0.09, LZ, dark);                  // 巾木
    box(side * (BELT_IN - 0.005), 0.008, 0, 0.012, 0.016, LZ, silver, false);       // ベルトの縁のアルミ
    box(side * (BELT_IN + BELT_W + 0.01), 0.008, 0, 0.012, 0.016, LZ, silver, false);
    // 外側のガラス壁(手すりの上)
    const gl = new THREE.Mesh(new THREE.PlaneGeometry(LZ, 0.6), new THREE.MeshStandardMaterial({ color: 0xaad0ff, transparent: true, opacity: 0.12, roughness: 0.05, metalness: 0, side: THREE.DoubleSide, depthWrite: false }));
    gl.rotation.y = Math.PI / 2; gl.position.set(side * (BELT_IN + BELT_W + 0.10), RAIL_TOP + 0.3, 0); add(gl);
  }
  const deck = new THREE.Mesh(new THREE.PlaneGeometry(2 * PANEL_IN, LZ), new THREE.MeshStandardMaterial({ map: deckT, color: 0x6a6e7c, roughness: 0.5, metalness: 0.7 }));
  deck.rotation.x = -Math.PI / 2; deck.position.set(0, 0.62, 0); deck.receiveShadow = true; add(deck);                 // すき間の底(影の中の暗い溝)
  const base = new THREE.Mesh(new THREE.PlaneGeometry(2 * TUN_R + 2, LZ), new THREE.MeshStandardMaterial({ color: 0x2a2b30, roughness: 0.45, metalness: 0.5 }));
  base.rotation.x = -Math.PI / 2; base.position.y = -0.01; base.receiveShadow = true; add(base);
  // アーチの鉄骨・ガラス天井・天井ライト・夜景
  const steel = new THREE.MeshStandardMaterial({ color: 0xb9bcc4, roughness: 0.28, metalness: 0.95 });
  for (let z = -LZ / 2; z <= LZ / 2; z += 1.6) {
    const rib = new THREE.Mesh(new THREE.TorusGeometry(TUN_R, 0.09, 12, 72, Math.PI), steel); rib.position.set(0, TUN_Y0, z); rib.castShadow = false; add(rib);
    for (const sx of [-1, 1]) { const p = new THREE.Mesh(new THREE.CylinderGeometry(0.06, 0.06, TUN_Y0, 10), steel); p.position.set(sx * TUN_R, TUN_Y0 / 2, z); add(p); }
  }
  const vault = new THREE.Mesh(new THREE.CylinderGeometry(TUN_R, TUN_R, LZ, 64, 1, true, Math.PI / 2, Math.PI), new THREE.MeshStandardMaterial({ color: 0x9fb4d8, transparent: true, opacity: 0.1, roughness: 0.05, side: THREE.DoubleSide, depthWrite: false }));
  vault.geometry.rotateX(Math.PI / 2); vault.position.y = TUN_Y0; add(vault);
  for (const sx of [-1, 1]) {
    const wall = new THREE.Mesh(new THREE.PlaneGeometry(LZ, TUN_Y0), new THREE.MeshStandardMaterial({ color: 0x9fb4d8, transparent: true, opacity: 0.1, roughness: 0.05, side: THREE.DoubleSide, depthWrite: false }));
    wall.rotation.y = Math.PI / 2; wall.position.set(sx * TUN_R, TUN_Y0 / 2, 0); add(wall);
  }
  const lamp = new THREE.MeshBasicMaterial({ color: 0xffdfae });                          // 天井の照明: リブごとの点
  for (let z = -LZ / 2; z <= LZ / 2; z += 0.8) for (const lx of [-2.2, -1.2, 0, 1.2, 2.2]) {
    const y = TUN_Y0 + Math.sqrt(TUN_R * TUN_R - lx * lx) - 0.12; const m = new THREE.Mesh(new THREE.SphereGeometry(0.045, 8, 6), lamp); m.position.set(lx, y, z); add(m);
  }
  const bcol = cityTexture(); bcol.repeat.set(3, 1);
  for (const sx of [-1, 1]) { const b = new THREE.Mesh(new THREE.PlaneGeometry(LZ * 1.2, 22), new THREE.MeshBasicMaterial({ map: bcol, color: 0x6c7080 })); b.rotation.y = -sx * Math.PI / 2; b.position.set(sx * 13, 6, 0); add(b); }
  { const b = new THREE.Mesh(new THREE.PlaneGeometry(60, 22), new THREE.MeshBasicMaterial({ map: bcol, color: 0x6c7080 })); b.position.set(0, 6, -30); add(b); const b2 = b.clone(); b2.position.z = 30; b2.rotation.y = Math.PI; add(b2); }
  // 反射用の環境マップ(トンネル全体を映す)。艶のある手すり・床に写り込む
  const cubeRT = new THREE.WebGLCubeRenderTarget(256, { type: THREE.HalfFloatType }), cubeCam = new THREE.CubeCamera(0.1, 100, cubeRT);
  cubeCam.position.set(0, 2.2, 0); scene3.add(cubeCam); cubeCam.update(renderer, scene3);
  const pm = new THREE.PMREMGenerator(renderer); scene3.environment = pm.fromCubemap(cubeRT.texture).texture; scene3.environmentIntensity = 0.9;

  // 丸い台(実現例)
  G.disc = new THREE.Group();
  const dm = new THREE.Mesh(new THREE.CylinderGeometry(0.6, 0.6, 0.04, 72), new THREE.MeshStandardMaterial({ color: 0x2f6fb0, roughness: 0.55 })); dm.castShadow = dm.receiveShadow = true;
  const ring = new THREE.Mesh(new THREE.TorusGeometry(0.5, 0.012, 8, 72), new THREE.MeshStandardMaterial({ color: 0xf2e6c2, roughness: 0.6 })); ring.rotation.x = Math.PI / 2; ring.position.y = 0.022;
  G.disc.add(dm, ring); G.disc.visible = false; scene3.add(G.disc);
  // ベルトに乗る人たち(左は手前へ、右は奥へ。手すりに手をのせて立つ)
  G.people = [];
  const LOOP = 18;
  for (const sgn of [-1, 1]) for (let k = 0; k < 7; k++) {
    const p = buildPerson(1000 + (sgn + 2) * 97 + k * 31, -1); p.userData.sgn = sgn; p.userData.z0 = k * (LOOP / 7) + (sgn > 0 ? 1.1 : 0);
    p.rotation.y = sgn < 0 ? 0 : Math.PI; scene3.add(p); G.people.push(p);
  }
  // キリン
  G.giraffe = buildGiraffe(); scene3.add(G.giraffe);
  // 残像・矢印・十字・寸法線・why の棒
  G.trails = [];
  for (let i = 0; i < 12; i++) { const m = new THREE.Mesh(new THREE.BoxGeometry(LEN, 0.004, 0.016), new THREE.MeshBasicMaterial({ color: 0x8ca5dc, transparent: true, opacity: 1 })); m.position.y = (RAIL_TOP + 0.008); m.visible = false; scene3.add(m); G.trails.push(m); }
  G.farr = [0, 1].map(() => {
    const g = new THREE.Group(), mat = new THREE.MeshBasicMaterial({ color: 0xe63228, depthTest: false });
    const shaft = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 1, 12), mat), head = new THREE.Mesh(new THREE.ConeGeometry(0.048, 0.079, 16), mat), dot = new THREE.Mesh(new THREE.SphereGeometry(0.027, 16, 12), mat);
    shaft.renderOrder = head.renderOrder = dot.renderOrder = 10; g.add(shaft, head, dot); g.userData = { shaft, head, dot }; g.visible = false; scene3.add(g); return g;
  });
  const yel = new THREE.MeshBasicMaterial({ color: 0xffd400, depthTest: false });
  G.cross = new THREE.Group(); for (const [a, b] of [[0.133, 0.015], [0.015, 0.133]]) { const m = new THREE.Mesh(new THREE.BoxGeometry(a, 0.004, b), yel); m.renderOrder = 11; G.cross.add(m); } G.cross.visible = false; scene3.add(G.cross);
  const red = new THREE.MeshBasicMaterial({ color: 0xc02e1c }); G.dim = new THREE.Group();
  const dl = new THREE.Mesh(new THREE.BoxGeometry(D, 0.004, 0.015), red); G.dim.add(dl);
  for (const sx of [-1, 1]) { const t = new THREE.Mesh(new THREE.BoxGeometry(0.015, 0.004, 0.109), red); t.position.x = sx * D / 2; G.dim.add(t); }
  G.dim.position.set(0, RAIL_TOP + 0.012, 210 / PPM); G.dim.visible = false; scene3.add(G.dim);
  G.bars = [[0, 0x2870e6], [45, 0x6e50c8], [72.9, 0xe63228]].map(([deg, col]) => {
    const th = deg * Math.PI / 180, len = D / Math.cos(th);
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, len, 20), new THREE.MeshStandardMaterial({ color: col, roughness: 0.4, emissive: col, emissiveIntensity: 0.18 }));
    m.rotation.z = Math.PI / 2; const grp = new THREE.Group(); grp.add(m); grp.rotation.y = th; grp.position.set(0, RAIL_TOP + 0.03, 30 / PPM);
    m.castShadow = true; grp.visible = false; scene3.add(grp); return grp;
  });
  return true;
}

function cameraRig(Tc, cx, cz, base) {
  // ドローンがキリンを中心に、ゆっくり回り込みながら舐めるように動き続ける。
  // 周期の長い正弦だけを重ねる(速い成分・手ぶれは入れない)ので、速度も加速度も連続で滑らか。Tc は3Dシーンだけをつないだ連続時計。
  const w = 2 * Math.PI;
  const yaw = 0.78 * Math.sin(w * Tc / 22.0) + 0.14 * Math.sin(w * Tc / 8.3 + 1.0);
  const pitch = 0.32 + 0.11 * Math.sin(w * Tc / 13.0 + 0.6);                // 真上から約18°±6°
  const dist = base + 0.12 * Math.sin(w * Tc / 10.0);
  const tx = cx + 0.08 * Math.sin(w * Tc / 12.0), tz = cz + 0.12 * Math.sin(w * Tc / 9.0 + 0.5);
  camera.position.set(tx + dist * Math.sin(pitch) * Math.sin(yaw), RAIL_TOP + dist * Math.cos(pitch), tz + dist * Math.sin(pitch) * Math.cos(yaw));
  camera.up.set(0, 1, 0); camera.lookAt(tx, RAIL_TOP, tz); camera.updateMatrixWorld();
}

function renderFrame(scene, t, T, k = 1) {
  const tu = t * k;
  const slow = 8.0;
  let ts = t, trails = false, forces = false, center = false, showG = true;
  if (scene === 'slowmo') { ts = t < TF * slow ? t / slow : TF + (t - TF * slow); trails = forces = center = true; }
  if (scene === 'why') { ts = 0; showG = false; }
  if (scene === 'setup') { showG = tu > 0.8; ts = t; }
  const demo = scene === 'demo'; if (demo) { ts = t; showG = true; center = true; }
  const fell = (scene === 'realtime' || scene === 'slowmo') && ts >= TF, st = state(Math.min(ts, TF));
  G.floorTex[0].offset.y = V * ts / 1.0; G.floorTex[1].offset.y = -V * ts / 1.0;           // 左は+Z(手前)へ、右は-Z(奥)へ
  G.railTex[0].offset.y = -V * ts / 0.35; G.railTex[1].offset.y = V * ts / 0.35;
  for (const p of G.people) {                                                // ベルトと一緒に動く利用者
    const sg = p.userData.sgn, LOOP = 18;
    p.position.set(sg * 1.19, 0, -9 + mod(p.userData.z0 + 9 - sg * V * ts, LOOP));
    const sw = Math.sin(p.userData.sway + T * 0.9); p.rotation.z = 0.015 * sw; p.userData.head.rotation.y = 0.25 * Math.sin(p.userData.sway * 2 + T * 0.35); p.userData.hair.rotation.y = p.userData.head.rotation.y;
  }
  G.disc.visible = demo;
  const gp = G.giraffe; gp.visible = showG;
  if (demo) {
    const th = DISC[Math.min(Math.round(t / 1e-3), DISC.length - 1)];
    G.disc.position.set(0, RAIL_TOP + 0.02, 0); G.disc.rotation.y = th;
    gp.position.set(0, RAIL_TOP + 0.04 + 0.11, 0); gp.rotation.y = th;
  } else if (showG) {
    let th = st[3], dropY = 0;
    if (scene === 'setup') th = 0;
    if (fell) { const k = ease((ts - TF) / 0.35); th += 0.15 * k; dropY = 0.36 * k; }
    gp.position.set(scene === 'setup' ? 0 : st[1], BODY_Y - dropY, scene === 'setup' ? 0 : -st[2]); gp.rotation.y = th;
  }
  G.cross.visible = center && !fell && false;
  G.cross.visible = center;
  if (center) { G.cross.position.set(demo ? 0 : st[1], RAIL_TOP + (demo ? 0.36 : 0.23), demo ? 0 : -st[2]); }
  let i = 0; for (const m of G.trails) { m.visible = false; m.material.opacity = 1; }
  if (demo) for (let j = 1; j <= 8; j++) {                                   // 残像: 0.12秒ごと、古いほど薄く
    const tt = t - j * 0.12; if (tt < 0) break; const m = G.trails[j - 1], a = DISC[Math.round(tt / 1e-3)];
    m.visible = true; m.position.set(0, RAIL_TOP + 0.075, 0); m.rotation.y = a; m.material.opacity = 0.7 * (1 - (j - 1) / 8);
  }
  if (trails) for (let k = 0.15; k < Math.min(ts, TF) && i < 12; k += 0.15, i++) {
    const s2 = state(k), m = G.trails[i]; m.visible = true; m.position.set(s2[1], (RAIL_TOP + 0.008), -s2[2]); m.rotation.y = s2[3];
  }
  G.farr.forEach((g, j) => {
    g.visible = forces && !fell; if (!g.visible) return;
    const si = j ? st[5] : st[4], fx = j ? st[8] : st[6], fy = j ? st[9] : st[7];
    const px = st[1] + si * Math.cos(st[3]), py = st[2] + si * Math.sin(st[3]);
    const dir = new THREE.Vector3(fx, 0, -fy), len = dir.length() * 0.9 / PPM; g.position.set(px, RAIL_TOP + 0.24, -py);
    const { shaft, head, dot } = g.userData;
    if (len < 0.012) { shaft.visible = head.visible = false; return; } shaft.visible = head.visible = true;
    dir.normalize(); const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    const sl = Math.max(0.001, len - 0.079); shaft.scale.set(1, sl, 1); shaft.position.copy(dir.clone().multiplyScalar(sl / 2)); shaft.quaternion.copy(q);
    head.position.copy(dir.clone().multiplyScalar(len - 0.0395)); head.quaternion.copy(q);
  });
  G.dim.visible = scene === 'setup';
  G.bars.forEach((b, i) => { const a = ease((tu - 0.4 - i * 1.4) / 0.5); b.visible = scene === 'why' && a > 0; b.scale.set(Math.max(a, 0.001), 1, 1); });
  let cz = 0; if (scene === 'why') cz = 30 / PPM;
  if (scene === 'dbg') { camera.position.set(t - 10, T, 6); camera.up.set(0, 1, 0); camera.lookAt(0, T * 0.6, -8); camera.updateMatrixWorld(); renderer.render(scene3, camera); return { label: [0, 0] }; }
  cameraRig(T, 0, cz, scene === 'why' ? 2.5 : (demo ? 3.0 : (scene === 'setup' ? 3.05 : 2.95)));
  renderer.render(scene3, camera);
  const lp = new THREE.Vector3(0, RAIL_TOP + 0.012, 210 / PPM + 52 / PPM * 1.15).project(camera);
  return { label: [(lp.x * 0.5 + 0.5) * W, (-lp.y * 0.5 + 0.5) * H] };
}
window.__ready = init().then(() => true);
window.renderFrame = renderFrame;
window.grab = () => renderer.domElement.toDataURL("image/jpeg", 0.9);
