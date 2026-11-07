// 動く歩道 × 仰向けの擬人化キリン(3D)。物理は sim.py の軌道(traj.json)をそのまま使う。
// world: X=x(右), Y=上, Z=-y(物理のy+が画面奥=北)
const PPM = 330, D = 0.5, V = 0.67, LEN = 1.70;
const RAIL_HW = 14 / PPM, GAP_HW = D / 2 - RAIL_HW;
const RAIL_TOP = 0.08, BODY_Y = 0.19;
const W = 720, H = 1280;
let TRAJ, TF, renderer, scene3, camera, G = {};
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
    ell(0.716, 0.088, sz * 0.064, 0.007, 0.006, 0.007, white);
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

async function init(aa = true) {
  renderer = new THREE.WebGLRenderer({ antialias: aa, preserveDrawingBuffer: true });
  renderer.setPixelRatio(1.5); renderer.setSize(W, H);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.05;
  renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  document.body.appendChild(renderer.domElement);
  TRAJ = await (await fetch('/web3d/traj.json')).json(); TF = TRAJ[TRAJ.length - 1][0];
  scene3 = new THREE.Scene(); scene3.background = new THREE.Color(0x9a9a98);
  camera = new THREE.PerspectiveCamera(52, W / H, 0.05, 80);

  const hemi = new THREE.HemisphereLight(0xdfeaff, 0x77716a, 0.95); scene3.add(hemi);
  const sun = new THREE.DirectionalLight(0xfff1dc, 2.6); sun.position.set(-3.2, 6.5, 3.0); sun.castShadow = true;
  sun.shadow.mapSize.set(4096, 4096); const sc = sun.shadow.camera; sc.left = -3.2; sc.right = 3.2; sc.top = 3.6; sc.bottom = -3.6; sc.near = 1; sc.far = 20;
  sun.shadow.bias = -0.0004; sun.shadow.normalBias = 0.02; sun.shadow.radius = 4; scene3.add(sun);

  const [floorT, railT, pitT, groundT] = await Promise.all([
    loadTex('painted_metal_shutter', [3.7, 60]), loadTex('rubber_tiles', [1, 60 / 0.35]),
    loadTex('worn_shutter', [1, 4]), loadTex('concrete_wall_004', [20, 20])]);
  G.floorTex = [floorT, floorT.clone()]; G.floorTex[1].needsUpdate = true;
  G.railTex = [railT, railT.clone()]; G.railTex[1].needsUpdate = true;
  const LZ = 60;
  for (const [i, side] of [[0, -1], [1, 1]]) {                               // 床
    const m = new THREE.Mesh(new THREE.PlaneGeometry(3.7, LZ), new THREE.MeshStandardMaterial({ map: G.floorTex[i], roughness: 0.55, metalness: 0.35, color: 0xf2f4f8 }));
    m.rotation.x = -Math.PI / 2; m.position.set(side * (D / 2 + RAIL_HW + 3.7 / 2 - 0.004), 0, 0); m.receiveShadow = true; scene3.add(m);
    const rail = new THREE.Mesh(new THREE.CylinderGeometry(RAIL_HW * 1.0, RAIL_HW * 1.0, LZ, 28), new THREE.MeshStandardMaterial({ map: G.railTex[i], roughness: 0.45, color: 0xffffff, emissive: 0x1c2850 }));
    rail.geometry.rotateX(Math.PI / 2); rail.scale.y = 0.62; rail.position.set(side * D / 2, RAIL_TOP - RAIL_HW * 0.62, 0);
    rail.castShadow = rail.receiveShadow = true; scene3.add(rail);
  }
  for (const sx of [-1, 1]) {
    const ground = new THREE.Mesh(new THREE.PlaneGeometry(40, 60), new THREE.MeshStandardMaterial({ map: groundT, roughness: 0.9 }));
    ground.rotation.x = -Math.PI / 2; ground.position.set(sx * (D / 2 + RAIL_HW + 3.7 + 20 - 0.01), -0.02, 0); ground.receiveShadow = true; scene3.add(ground);
  }
  // すき間(深い穴)
  const pitMat = new THREE.MeshStandardMaterial({ map: pitT, color: 0x8088a8, emissive: 0x14142c, roughness: 0.8, side: THREE.DoubleSide });
  for (const sx of [-1, 1]) { const w = new THREE.Mesh(new THREE.PlaneGeometry(LZ, 1.4), pitMat); w.rotation.y = Math.PI / 2; w.position.set(sx * GAP_HW, -0.7, 0); w.receiveShadow = true; scene3.add(w); }
  const pb = new THREE.Mesh(new THREE.PlaneGeometry(2 * GAP_HW, LZ), new THREE.MeshStandardMaterial({ color: 0x10101a, emissive: 0x0a0a18, roughness: 1 })); pb.rotation.x = -Math.PI / 2; pb.position.y = -1.4; pb.receiveShadow = true; scene3.add(pb);

  // 床の矢印(塗装)・手すりの目印(山吹色)
  const triShape = new THREE.Shape(); triShape.moveTo(0, 26 / PPM); triShape.lineTo(-18 / PPM, -5.2 / PPM); triShape.lineTo(18 / PPM, -5.2 / PPM); triShape.closePath();
  const arrowMat = new THREE.MeshBasicMaterial({ color: 0xece8d6, transparent: true, opacity: 0.8, depthWrite: false, polygonOffset: true, polygonOffsetFactor: -2 });
  G.arrows = []; const NA = 22;
  for (const sgn of [-1, 1]) for (let k = 0; k < NA; k++) {
    const m = new THREE.Mesh(new THREE.ShapeGeometry(triShape), arrowMat); m.rotation.x = -Math.PI / 2; if (sgn < 0) m.rotation.z = Math.PI;
    m.position.x = sgn * (D / 2 + 110 / PPM); scene3.add(m); G.arrows.push({ m, sgn, k });
  }
  const dotMat = new THREE.MeshStandardMaterial({ color: 0xecba30, roughness: 0.4 }); G.dots = [];
  for (const sgn of [-1, 1]) for (let k = 0; k < 132; k++) {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.016, 12, 8), dotMat); m.scale.y = 0.5; m.position.x = sgn * D / 2; scene3.add(m); G.dots.push({ m, sgn, k });
  }
  // キリン
  G.giraffe = buildGiraffe(); scene3.add(G.giraffe);
  // 残像・矢印・十字・寸法線・why の棒
  G.trails = []; const trMat = new THREE.MeshBasicMaterial({ color: 0x8ca5dc });
  for (let i = 0; i < 12; i++) { const m = new THREE.Mesh(new THREE.BoxGeometry(LEN, 0.004, 0.016), trMat); m.position.y = 0.088; m.visible = false; scene3.add(m); G.trails.push(m); }
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
  G.dim.position.set(0, 0.092, 210 / PPM); G.dim.visible = false; scene3.add(G.dim);
  G.bars = [[0, 0x2870e6], [45, 0x6e50c8], [72.9, 0xe63228]].map(([deg, col]) => {
    const th = deg * Math.PI / 180, len = D / Math.cos(th);
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.018, len, 20), new THREE.MeshStandardMaterial({ color: col, roughness: 0.4, emissive: col, emissiveIntensity: 0.18 }));
    m.rotation.z = Math.PI / 2; const grp = new THREE.Group(); grp.add(m); grp.rotation.y = th; grp.position.set(0, 0.11, 30 / PPM);
    m.castShadow = true; grp.visible = false; scene3.add(grp); return grp;
  });
  return true;
}

function cameraRig(T, cx, cz, th = 0, base = null) {
  const yaw = 0.32 * Math.sin(2 * Math.PI * T / 17.0), pitch = 0.24 + 0.15 * Math.sin(2 * Math.PI * T / 11.0 + 1.0);
  const need = base ?? (4.05 - 1.05 * Math.abs(Math.sin(th))), dist = need + 0.25 * Math.sin(2 * Math.PI * T / 13.0);
  const tx = cx + 0.12 * Math.sin(2 * Math.PI * T / 9.0), tz = cz + 0.22 * Math.sin(2 * Math.PI * T / 7.0 + 0.5);
  const sh = 0.004 * Math.sin(T * 9.1) + 0.003 * Math.sin(T * 17.3);                      // ドローンのわずかな揺れ
  camera.position.set(tx + dist * Math.sin(pitch) * Math.sin(yaw) + sh, dist * Math.cos(pitch), tz + dist * Math.sin(pitch) * Math.cos(yaw) + sh);
  camera.up.set(0, 1, 0); camera.lookAt(tx, 0, tz); camera.updateMatrixWorld();
}

function renderFrame(scene, t, T) {
  const slow = 8.0;
  let ts = t, trails = false, forces = false, center = false, showG = true;
  if (scene === 'slowmo') { ts = t < TF * slow ? t / slow : TF + (t - TF * slow); trails = forces = center = true; }
  if (scene === 'why') { ts = 0; showG = false; }
  if (scene === 'setup') { showG = t > 0.8; ts = t; }
  const fell = (scene === 'realtime' || scene === 'slowmo') && ts >= TF, st = state(Math.min(ts, TF));
  for (const a of G.arrows) {
    const sp = 240 / PPM, N = 22; a.m.position.set(a.m.position.x, 0.003, -8 + mod(a.k * sp - a.sgn * V * ts, N * sp));
    a.m.visible = scene !== 'why' || true;
  }
  for (const d of G.dots) { const sp = 40 / PPM; d.m.position.set(d.sgn * D / 2, RAIL_TOP + 0.002, -8 + mod(d.k * sp - d.sgn * V * ts, 132 * sp)); }
  G.floorTex[0].offset.y = V * ts / 1.0; G.floorTex[1].offset.y = -V * ts / 1.0;           // 左は+Z(手前)へ、右は-Z(奥)へ
  G.railTex[0].offset.y = -V * ts / 0.35; G.railTex[1].offset.y = V * ts / 0.35;
  const gp = G.giraffe; gp.visible = showG;
  if (showG) {
    let th = st[3], dropY = 0;
    if (scene === 'setup') th = 0;
    if (fell) { const k = ease((ts - TF) / 0.35); th += 0.15 * k; dropY = 1.35 * k; }
    gp.position.set(scene === 'setup' ? 0 : st[1], BODY_Y - dropY, scene === 'setup' ? 0 : -st[2]); gp.rotation.y = th;
  }
  G.cross.visible = center && !fell && false;
  G.cross.visible = center;
  if (center) { G.cross.position.set(st[1], 0.31, -st[2]); }
  let i = 0; for (const m of G.trails) m.visible = false;
  if (trails) for (let k = 0.15; k < Math.min(ts, TF) && i < 12; k += 0.15, i++) {
    const s2 = state(k), m = G.trails[i]; m.visible = true; m.position.set(s2[1], 0.088, -s2[2]); m.rotation.y = s2[3];
  }
  G.farr.forEach((g, j) => {
    g.visible = forces && !fell; if (!g.visible) return;
    const si = j ? st[5] : st[4], fx = j ? st[8] : st[6], fy = j ? st[9] : st[7];
    const px = st[1] + si * Math.cos(st[3]), py = st[2] + si * Math.sin(st[3]);
    const dir = new THREE.Vector3(fx, 0, -fy), len = dir.length() * 0.9 / PPM; g.position.set(px, 0.32, -py);
    const { shaft, head, dot } = g.userData;
    if (len < 0.012) { shaft.visible = head.visible = false; return; } shaft.visible = head.visible = true;
    dir.normalize(); const q = new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), dir);
    const sl = Math.max(0.001, len - 0.079); shaft.scale.set(1, sl, 1); shaft.position.copy(dir.clone().multiplyScalar(sl / 2)); shaft.quaternion.copy(q);
    head.position.copy(dir.clone().multiplyScalar(len - 0.0395)); head.quaternion.copy(q);
  });
  G.dim.visible = scene === 'setup';
  G.bars.forEach((b, i) => { const a = ease((t - 0.4 - i * 1.4) / 0.5); b.visible = scene === 'why' && a > 0; b.scale.set(Math.max(a, 0.001), 1, 1); });
  let cz = 0; if (scene === 'why') cz = 30 / PPM;
  cameraRig(T, 0, cz, scene === 'setup' ? 0 : (scene === 'why' ? 0 : st[3]), scene === 'why' ? 3.4 : null);
  renderer.render(scene3, camera);
  const lp = new THREE.Vector3(0, 0.09, 210 / PPM + 52 / PPM * 1.15).project(camera);
  return { label: [(lp.x * 0.5 + 0.5) * W, (-lp.y * 0.5 + 0.5) * H] };
}
window.__ready = init().then(() => true);
window.renderFrame = renderFrame;
window.grab = () => renderer.domElement.toDataURL("image/jpeg", 0.9);
