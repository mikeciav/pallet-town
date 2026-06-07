// Three.js 3D pallet visualization — loaded via CDN importmap, no build step.
// Variants: A=static isometric, B=layer-reveal, C=free-orbit perspective
// Activated by the 3D toggle; ?view=A/B/C in the URL tracks the active variant.
// Press ←/→ arrow keys to cycle variants.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ── Constants ─────────────────────────────────────────────────────────────────
const VARIANT_NAMES = { A: 'Isometric', B: 'Layers', C: 'Orbit' };
const BG_DARK = 0x0d1119;

// ── Singleton state ───────────────────────────────────────────────────────────
let _renderer   = null;
let _controls   = null;
let _animId     = null;
let _keyHandler = null;

function dispose() {
  if (_animId !== null)  { cancelAnimationFrame(_animId); _animId = null; }
  if (_controls)         { _controls.dispose(); _controls = null; }
  if (_renderer)         { _renderer.dispose(); _renderer = null; }
  if (_keyHandler)       { document.removeEventListener('keydown', _keyHandler); _keyHandler = null; }
  document.getElementById('diagram-switcher')?.remove();
  document.getElementById('p3d-layer-ctrl')?.remove();
}

// ── Scene helpers ─────────────────────────────────────────────────────────────
function buildBaseScene(d) {
  const { pallet_length: PL, pallet_width: PW } = d;
  const scene  = new THREE.Scene();
  const palGeo = new THREE.BoxGeometry(PL, 4, PW);
  const palMat = new THREE.MeshLambertMaterial({ color: 0x667788 });
  const pallet = new THREE.Mesh(palGeo, palMat);
  pallet.position.set(PL / 2, -2, PW / 2);
  scene.add(pallet);
  return scene;
}

function addStandardLighting(scene, d) {
  const { pallet_length: PL, pallet_width: PW, hi, case_h: CH } = d;
  const stackH = hi * CH;
  scene.add(new THREE.AmbientLight(0xffffff, 0.45));
  const sun  = new THREE.DirectionalLight(0xffffff, 1.4);
  sun.position.set(PL * 2, stackH * 2.5, -PW);
  scene.add(sun);
  const fill = new THREE.DirectionalLight(0x8899cc, 0.5);
  fill.position.set(-PL, stackH, PW * 2);
  scene.add(fill);
}

const SIDE_COLORS = { top: 0xa78bfa, right: 0x67e8f9, bottom: 0x86efac, left: 0xfbbf24 };

// Returns array of box meshes added to scene.
// opts.byLayer:  colour by layer index (cool→warm gradient)
// opts.bySide:   colour by c.side (shoppable view)
// opts.edges:    add EdgesGeometry overlay (default true)
// opts.arrangement: override which arrangement array to use
function addBoxMeshes(scene, d, opts = {}) {
  const arrangement = opts.arrangement ?? d.arrangement;
  const { hi, case_h: CH } = d;
  const withEdges = opts.edges !== false;
  const edgeMat  = new THREE.LineBasicMaterial({ color: 0x000000, transparent: true, opacity: 0.28 });
  const meshes   = [];

  arrangement.forEach(c => {
    for (let layer = 0; layer < hi; layer++) {
      let col;
      if (opts.bySide) {
        col = new THREE.Color(SIDE_COLORS[c.side] ?? 0x8899aa);
      } else if (opts.byLayer) {
        const t = hi > 1 ? layer / (hi - 1) : 0;
        col = new THREE.Color(0x4488ff).lerp(new THREE.Color(0xff8833), t);
      } else {
        col = c.rotated ? new THREE.Color(0xb8d4ff) : new THREE.Color(0xffd4b8);
      }
      const geo  = new THREE.BoxGeometry(c.w - 0.3, CH - 0.3, c.h - 0.3);
      const mat  = new THREE.MeshLambertMaterial({ color: col });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.set(c.x + c.w / 2, layer * CH + CH / 2, c.y + c.h / 2);
      mesh.userData.layer = layer;
      scene.add(mesh);
      meshes.push(mesh);

      if (withEdges) {
        const e = new THREE.LineSegments(new THREE.EdgesGeometry(geo), edgeMat);
        e.position.copy(mesh.position);
        e.userData.layer = layer;
        scene.add(e);
        mesh.userData.edgeLines = e;
      }
    }
  });

  return meshes;
}

// ── Camera helpers ────────────────────────────────────────────────────────────
function makeOrthoCamera(d, W, H) {
  const { pallet_length: PL, pallet_width: PW, hi, case_h: CH } = d;
  const cx = PL / 2, cy = hi * CH / 2, cz = PW / 2;
  // Bounding radius of the scene (pallet base at -4 to stack top)
  const r  = Math.sqrt((PL / 2) ** 2 + ((hi * CH + 4) / 2) ** 2 + (PW / 2) ** 2) * 1.35;
  const cam = new THREE.OrthographicCamera(
    -(r * W / H), (r * W / H), r, -r, 0.1, r * 20
  );
  const D = r * 3;
  cam.position.set(cx + D, cy + D * 0.9, cz + D);
  cam.lookAt(cx, cy * 0.5, cz);
  return cam;
}

function makePerspCamera(d, W, H) {
  const { pallet_length: PL, pallet_width: PW, hi, case_h: CH } = d;
  const cx = PL / 2, cz = PW / 2;
  const D  = Math.max(PL, PW, hi * CH) * 2;
  const cam = new THREE.PerspectiveCamera(45, W / H, 0.1, 10000);
  cam.position.set(cx + D * 0.8, hi * CH * 0.6 + D * 0.6, cz + D * 0.8);
  cam.lookAt(cx, hi * CH * 0.35, cz);
  return cam;
}

// ── Variant A: Static Isometric Orthographic ──────────────────────────────────
// Closest to the onpallet.com aesthetic — fixed angle, clean depth, no interaction.
function renderVariantA(d, box) {
  const W = box.clientWidth, H = box.clientHeight;
  box.innerHTML = '<canvas style="width:100%;height:100%;display:block"></canvas>';
  const canvas = box.querySelector('canvas');

  _renderer = makeRenderer(canvas, W, H, BG_DARK);

  const scene = buildBaseScene(d);
  addStandardLighting(scene, d);
  addBoxMeshes(scene, d, { arrangement: d._arrangement, bySide: d._bySide });

  _renderer.render(scene, makeOrthoCamera(d, W, H));
}

// ── Variant B: Layer-by-Layer Reveal ─────────────────────────────────────────
// Boxes coloured by layer (cool→warm). Step through layers with − / + buttons.
// Useful for verifying that each layer is laid out correctly.
function renderVariantB(d, box) {
  const W = box.clientWidth, H = box.clientHeight;
  const { hi } = d;
  let visible = hi;

  box.innerHTML = '<canvas style="width:100%;height:100%;display:block"></canvas>';
  const canvas = box.querySelector('canvas');

  // Layer control strip
  const ctrl = document.createElement('div');
  ctrl.id = 'p3d-layer-ctrl';
  ctrl.style.cssText = `
    position:absolute;bottom:48px;left:50%;transform:translateX(-50%);
    display:flex;align-items:center;gap:8px;
    background:rgba(13,17,25,0.9);border:1px solid #253047;border-radius:4px;
    padding:4px 12px;font-family:JetBrains Mono,monospace;font-size:11px;
    color:#7a95b0;user-select:none;z-index:10;pointer-events:all;
  `;
  ctrl.innerHTML = `
    <button id="p3d-less" style="background:none;border:none;color:#7a95b0;cursor:pointer;font-size:16px;padding:0 3px;line-height:1">−</button>
    <span id="p3d-lbl">${hi}&thinsp;/&thinsp;${hi} layers</span>
    <button id="p3d-more" style="background:none;border:none;color:#7a95b0;cursor:pointer;font-size:16px;padding:0 3px;line-height:1">+</button>
  `;
  box.appendChild(ctrl);

  _renderer = makeRenderer(canvas, W, H, BG_DARK);

  const scene  = buildBaseScene(d);
  addStandardLighting(scene, d);
  const meshes = addBoxMeshes(scene, d, { arrangement: d._arrangement, byLayer: true });
  const camera = makeOrthoCamera(d, W, H);

  function render() {
    meshes.forEach(m => {
      const on = m.userData.layer < visible;
      m.visible = on;
      if (m.userData.edgeLines) m.userData.edgeLines.visible = on;
    });
    document.getElementById('p3d-lbl').textContent = `${visible} / ${hi} layers`;
    _renderer.render(scene, camera);
  }

  ctrl.querySelector('#p3d-less').addEventListener('click', () => { if (visible > 1) { visible--; render(); } });
  ctrl.querySelector('#p3d-more').addEventListener('click', () => { if (visible < hi) { visible++; render(); } });

  render();
}

// ── Variant C: Free-Orbit Perspective ─────────────────────────────────────────
// Full WebGL scene with PerspectiveCamera + OrbitControls.
// Auto-rotates until the user interacts. Shows a floor grid for spatial context.
function renderVariantC(d, box) {
  const W = box.clientWidth, H = box.clientHeight;
  const { pallet_length: PL, pallet_width: PW, hi, case_h: CH } = d;
  const cx = PL / 2, cz = PW / 2, targetY = hi * CH * 0.35;

  box.innerHTML = `
    <canvas style="width:100%;height:100%;display:block;touch-action:none"></canvas>
    <div style="position:absolute;bottom:44px;left:50%;transform:translateX(-50%);
      font-family:JetBrains Mono,monospace;font-size:9px;color:#3d5068;
      pointer-events:none;white-space:nowrap">drag · scroll · right-click pan</div>
  `;
  const canvas = box.querySelector('canvas');

  _renderer = makeRenderer(canvas, W, H, 0x080c12);
  _renderer.shadowMap.enabled = true;
  _renderer.shadowMap.type    = THREE.PCFSoftShadowMap;

  const scene = buildBaseScene(d);
  scene.add(new THREE.AmbientLight(0xffffff, 0.32));

  const sun = new THREE.DirectionalLight(0xfff5e0, 1.8);
  sun.position.set(PL, hi * CH * 3, -PW);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  scene.add(sun);

  const fill = new THREE.DirectionalLight(0xaabbdd, 0.55);
  fill.position.set(-PL, hi * CH, PW * 2);
  scene.add(fill);

  // Floor grid
  const gridSize = Math.max(PL, PW) * 2.5;
  const grid = new THREE.GridHelper(gridSize, 14, 0x1a2436, 0x1a2436);
  grid.position.set(cx, -4.1, cz);
  scene.add(grid);

  addBoxMeshes(scene, d, { arrangement: d._arrangement, bySide: d._bySide, edges: true });

  const camera = makePerspCamera(d, W, H);

  _controls = new OrbitControls(camera, canvas);
  _controls.target.set(cx, targetY, cz);
  _controls.enableDamping  = true;
  _controls.dampingFactor  = 0.08;
  _controls.autoRotate     = true;
  _controls.autoRotateSpeed = 0.55;
  _controls.minDistance    = Math.max(PL, PW) * 0.5;
  _controls.maxDistance    = Math.max(PL, PW, hi * CH) * 8;
  _controls.addEventListener('start', () => { _controls.autoRotate = false; });
  _controls.update();

  (function animate() {
    _animId = requestAnimationFrame(animate);
    _controls.update();
    _renderer.render(scene, camera);
  })();
}

// ── WebGL renderer factory ────────────────────────────────────────────────────
function makeRenderer(canvas, W, H, clearColor) {
  const r = new THREE.WebGLRenderer({ canvas, antialias: true });
  r.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  r.setSize(W, H);
  r.setClearColor(clearColor);
  return r;
}

// ── Switcher UI ───────────────────────────────────────────────────────────────
function getVariant() {
  return new URLSearchParams(location.search).get('view');
}

function setVariant(v) {
  const u = new URL(location.href);
  v ? u.searchParams.set('view', v) : u.searchParams.delete('view');
  history.replaceState(null, '', u);
  if (window._lastResult) window.drawDiagram(window._lastResult);
}

function buildSwitcher(box, active) {
  document.getElementById('diagram-switcher')?.remove();

  const sw = document.createElement('div');
  sw.id = 'diagram-switcher';
  sw.style.cssText = `
    position:absolute;bottom:8px;left:50%;transform:translateX(-50%);
    display:flex;align-items:center;gap:5px;
    background:rgba(13,17,25,0.92);border:1px solid #253047;
    border-radius:20px;padding:4px 10px;
    font-family:JetBrains Mono,monospace;font-size:10px;
    color:#7a95b0;user-select:none;pointer-events:all;z-index:10;
  `;

  ['A', 'B', 'C'].forEach(v => {
    const on  = v === active;
    const btn = document.createElement('button');
    btn.textContent = `${v} — ${VARIANT_NAMES[v]}`;
    btn.style.cssText = `
      background:${on ? 'rgba(251,191,36,0.12)' : 'none'};
      border:1px solid ${on ? 'rgba(251,191,36,0.4)' : 'transparent'};
      color:${on ? '#fbbf24' : '#7a95b0'};
      border-radius:12px;padding:2px 8px;cursor:pointer;
      font-family:inherit;font-size:inherit;
    `;
    btn.addEventListener('click', () => setVariant(v));
    sw.appendChild(btn);
  });

  box.appendChild(sw);

  _keyHandler = e => {
    if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) return;
    const v  = getVariant();
    if (!v) return;
    const vs = ['A', 'B', 'C'];
    const i  = vs.indexOf(v);
    if (e.key === 'ArrowLeft'  && i > 0)             setVariant(vs[i - 1]);
    if (e.key === 'ArrowRight' && i < vs.length - 1) setVariant(vs[i + 1]);
  };
  document.addEventListener('keydown', _keyHandler);
}

// ── Main entry point ──────────────────────────────────────────────────────────
function viewDraw(d, box) {
  const v = getVariant();
  if (!v || !d.hi) return false;

  // Shoppable results have their arrangement under d.shoppable.arrangement
  const isShoppable  = !!(d.shoppable?.arrangement?.length);
  const arrangement  = isShoppable ? d.shoppable.arrangement : d.arrangement;
  if (!arrangement?.length) return false;

  // Attach the resolved arrangement + color mode to a context object passed to renderers
  const ctx = { ...d, _arrangement: arrangement, _bySide: isShoppable };

  dispose();

  if      (v === 'A') renderVariantA(ctx, box);
  else if (v === 'B') renderVariantB(ctx, box);
  else if (v === 'C') renderVariantC(ctx, box);

  buildSwitcher(box, v);
  return true;
}

// ── Initialise on DOM ready ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  window._draw3d = viewDraw;
});
