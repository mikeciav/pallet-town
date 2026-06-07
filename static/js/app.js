/* ============================================================
   Pallet Town — frontend logic
   ============================================================ */

const API = {
  retailers:      '/api/retailers',
  retailer:  (id) => `/api/retailers/${id}`,
  retailerNotes: (id) => `/api/retailers/${id}/notes`,
  calculate:      '/api/calculate',
  bulkCalc:       '/api/calculate-bulk',
};

let retailers   = [];
let bulkData    = [];
let bulkResults = [];
let lastResult  = null;
let diagramView = 'ti';
let isAdmin     = false;
let customRetailer = { max_height: 60, double_stack_allowed: false, max_pallets_per_floor: 26, no_pallet: false };

function loadCustomRetailer() {
  try {
    const saved = localStorage.getItem('custom-retailer');
    if (saved) customRetailer = { ...customRetailer, ...JSON.parse(saved) };
  } catch {}
}

function saveCustomRetailer() {
  localStorage.setItem('custom-retailer', JSON.stringify(customRetailer));
}

function readCustomEditorValues(prefix) {
  const maxh    = parseFloat(document.getElementById(`${prefix}-maxh`).value);
  const pallets = parseInt(document.getElementById(`${prefix}-pallets`).value, 10);
  if (!isNaN(maxh) && maxh > 0)       customRetailer.max_height            = maxh;
  if (!isNaN(pallets) && pallets > 0) customRetailer.max_pallets_per_floor = pallets;
  customRetailer.double_stack_allowed = document.getElementById(`${prefix}-ds`).checked;
  customRetailer.no_pallet            = document.getElementById(`${prefix}-nopallet`).checked;
  saveCustomRetailer();
  syncCustomEditors();
}

function syncCustomEditors() {
  [['ie-maxh', 'ie-pallets', 'ie-ds', 'ie-nopallet'],
   ['bulk-ie-maxh', 'bulk-ie-pallets', 'bulk-ie-ds', 'bulk-ie-nopallet']].forEach(([mh, pl, ds, np]) => {
    const mhEl = document.getElementById(mh);
    if (!mhEl) return;
    mhEl.value                                  = customRetailer.max_height;
    document.getElementById(pl).value           = customRetailer.max_pallets_per_floor;
    document.getElementById(ds).checked         = customRetailer.double_stack_allowed;
    document.getElementById(np).checked         = customRetailer.no_pallet;
  });
}

// ── Helpers (loaded early — used throughout) ─────────────────
function debounce(fn, ms) {
  let t;
  return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
}

function showToast(msg = 'Config saved') {
  // Reuse an existing toast if one is already showing
  let el = document.querySelector('.toast');
  if (!el) {
    el = document.createElement('div');
    el.className = 'toast';
    document.body.appendChild(el);
  }
  el.textContent = msg;
  el.classList.add('visible');
  clearTimeout(el._hideTimer);
  el._hideTimer = setTimeout(() => {
    el.classList.remove('visible');
    setTimeout(() => el.remove(), 200);
  }, 1800);
}

// ── Bootstrap ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  loadCustomRetailer();
  setupSidebarToggle();
  setupNav();
  setupAuth();
  await checkAuth();
  await loadRetailers();
  setupCalculator();
  setupBulk();
  setupRetailersTab();
  if (window.SHOW_DEMO_DEFAULTS) doCalculate();
});

// ── Sidebar collapse ─────────────────────────────────────────
function setupSidebarToggle() {
  const btn     = document.getElementById('sidebar-toggle');
  const sidebar = document.querySelector('.sidebar');
  const main    = document.querySelector('.main');

  const apply = (collapsed) => {
    sidebar.classList.toggle('sidebar--collapsed', collapsed);
    main.classList.toggle('main--collapsed', collapsed);
    btn.title = collapsed ? 'Expand sidebar' : 'Collapse sidebar';
  };

  apply(localStorage.getItem('sidebar-collapsed') === 'true');

  btn.addEventListener('click', () => {
    const collapsed = !sidebar.classList.contains('sidebar--collapsed');
    apply(collapsed);
    localStorage.setItem('sidebar-collapsed', collapsed);
  });
}

// ── Navigation ───────────────────────────────────────────────
function setupNav() {
  const navItems = [...document.querySelectorAll('.nav-item')];
  const TITLES = {
    calculator: 'PALLET BUILDER',
    bulk:       'BULK IMPORT',
    retailers:  'RETAILER CONFIGURATIONS',
  };

  navItems.forEach(btn => {
    btn.addEventListener('click', () => {
      navItems.forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
      btn.classList.add('active');
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');
      document.getElementById('page-title').textContent = TITLES[btn.dataset.tab] || '';
      // Refresh retailer info on the newly visible tab so notes/config stay in sync
      if (btn.dataset.tab === 'calculator') updateInfoBar();
      if (btn.dataset.tab === 'bulk')       refreshBulkRetailerInfo();
      if (btn.dataset.tab === 'retailers' && selectedRetailerId) {
        const _r = retailerById(selectedRetailerId);
        if (_r) renderRetailerDetail(_r);
      }
    });
  });
}

// ── Auth ─────────────────────────────────────────────────────
function setupAuth() {
  document.getElementById('auth-btn').addEventListener('click', () => {
    if (isAdmin) {
      doLogout();
    } else {
      openLoginModal();
    }
  });
  document.getElementById('login-cancel').addEventListener('click', closeLoginModal);
  document.getElementById('login-submit').addEventListener('click', doLogin);
  document.getElementById('login-pw').addEventListener('keydown', e => {
    if (e.key === 'Enter') doLogin();
  });
  document.getElementById('login-modal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeLoginModal();
  });
}

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/status');
    const data = await res.json();
    isAdmin = data.is_admin;
    updateAuthUI();
  } catch { /* network error — stay locked */ }
}

function openLoginModal() {
  document.getElementById('login-pw').value = '';
  document.getElementById('login-error').textContent = '';
  document.getElementById('login-modal').style.display = 'flex';
  setTimeout(() => document.getElementById('login-pw').focus(), 50);
}

function closeLoginModal() {
  document.getElementById('login-modal').style.display = 'none';
}

async function doLogin() {
  const pw = document.getElementById('login-pw').value;
  document.getElementById('login-btn-text').textContent = 'CHECKING…';
  document.getElementById('login-submit').disabled = true;
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: pw }),
    });
    if (res.ok) {
      isAdmin = true;
      updateAuthUI();
      closeLoginModal();
    } else {
      const d = await res.json();
      document.getElementById('login-error').textContent = d.error || 'Incorrect password';
    }
  } catch {
    document.getElementById('login-error').textContent = 'Connection error';
  } finally {
    document.getElementById('login-btn-text').textContent = 'AUTHENTICATE';
    document.getElementById('login-submit').disabled = false;
  }
}

async function doLogout() {
  await fetch('/api/auth/logout', { method: 'POST' });
  isAdmin = false;
  updateAuthUI();
}

function updateAuthUI() {
  const btn     = document.getElementById('auth-btn');
  const btnText = document.getElementById('auth-btn-text');
  const icon    = btn.querySelector('.auth-icon');

  if (isAdmin) {
    btnText.textContent = 'Admin';
    btn.classList.add('auth-btn--active');
    // swap lock → unlock icon
    icon.innerHTML = '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 9.9-1"/>';
  } else {
    btnText.textContent = 'Admin Login';
    btn.classList.remove('auth-btn--active');
    icon.innerHTML = '<rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>';
  }

  // Lock / unlock retailer detail panel
  const locked = !isAdmin;
  ['rd-name', 'rd-maxh', 'rd-pallets', 'rd-ds', 'rd-np', 'rd-notes'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.disabled = locked;
  });
  const rdDel = document.getElementById('rd-delete');
  if (rdDel) rdDel.style.visibility = locked ? 'hidden' : 'visible';
  const addBtn = document.getElementById('add-retailer-btn');
  if (addBtn) addBtn.style.visibility = locked ? 'hidden' : 'visible';

}

// ── Retailers API ────────────────────────────────────────────
async function loadRetailers() {
  try {
    const res = await fetch(API.retailers);
    retailers = await res.json();
    syncRetailerSelects();
    renderRetailersGrid();
    // Temporary defaults: pre-select Costco
    const sel = document.getElementById('retailer-select');
    if (!sel.value) { sel.value = '3'; updateInfoBar(); }
    updateClubPanel();
  } catch (e) {
    setStatus('Could not load retailers.', true);
  }
}

function syncRetailerSelects() {
  ['retailer-select', 'bulk-retailer'].forEach(id => {
    const sel = document.getElementById(id);
    const cur = sel.value;
    sel.innerHTML = '<option value="">— Select Retailer —</option>';
    const customOpt = document.createElement('option');
    customOpt.value = 'custom';
    customOpt.textContent = 'Custom';
    sel.appendChild(customOpt);
    retailers.forEach(r => {
      const o = document.createElement('option');
      o.value = r.id;
      o.textContent = r.name;
      sel.appendChild(o);
    });
    if (cur) sel.value = cur;
  });
}

function retailerById(id) {
  return retailers.find(r => String(r.id) === String(id));
}

// ── Single Calculator ────────────────────────────────────────
function setupCalculator() {
  document.getElementById('retailer-select').addEventListener('change', () => {
    updateInfoBar();
    updateClubPanel();
  });
  document.getElementById('calc-btn').addEventListener('click', doCalculate);
  document.getElementById('clear-btn').addEventListener('click', () => {
    ['c-l', 'c-w', 'c-h', 'c-cw', 'c-cp'].forEach(id => {
      document.getElementById(id).value = '';
    });
  });

  document.querySelectorAll('.vt-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      diagramView = btn.dataset.view;
      document.querySelectorAll('.vt-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      if (lastResult) drawDiagram(lastResult);
    });
  });
  ['c-l', 'c-w', 'c-h'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => {
      if (e.key === 'Enter') doCalculate();
    });
  });

  // Retailer notes (editable for all users, all retailers)
  const debouncedCalcNotes = debounce(() => saveRetailerNotes('calc-retailer-notes', 'retailer-select'), 800);
  document.getElementById('calc-retailer-notes').addEventListener('input', debouncedCalcNotes);
  document.getElementById('calc-retailer-notes').addEventListener('blur', () => saveRetailerNotes('calc-retailer-notes', 'retailer-select'));

  // Custom retailer editor: update shared state on change
  const debouncedIESave = debounce(() => readCustomEditorValues('ie'), 500);
  ['ie-maxh', 'ie-pallets'].forEach(id => {
    document.getElementById(id).addEventListener('input', debouncedIESave);
    document.getElementById(id).addEventListener('blur', () => readCustomEditorValues('ie'));
  });
  document.getElementById('ie-ds').addEventListener('change', () => readCustomEditorValues('ie'));
  document.getElementById('ie-nopallet').addEventListener('change', () => readCustomEditorValues('ie'));

  // Inline editor: collapse toggle
  document.getElementById('ie-toggle').addEventListener('click', () => {
    const body   = document.getElementById('ie-body');
    const toggle = document.getElementById('ie-toggle');
    const collapsed = body.style.display === 'none';
    body.style.display = collapsed ? 'block' : 'none';
    toggle.textContent = collapsed ? '▲' : '▼';
  });

  setupSideSelector();
}


function updateInfoBar() {
  const rid      = document.getElementById('retailer-select').value;
  const editor   = document.getElementById('inline-editor');
  const notesWrap = document.getElementById('calc-notes-wrap');
  if (!rid) { editor.style.display = 'none'; notesWrap.style.display = 'none'; return; }

  const isCustom = rid === 'custom';
  editor.querySelector('.panel-label').textContent = isCustom ? 'CUSTOM RETAILER' : 'RETAILER DETAILS';
  ['ie-maxh', 'ie-pallets', 'ie-ds', 'ie-nopallet'].forEach(id => {
    document.getElementById(id).disabled = !isCustom;
  });

  if (isCustom) {
    syncCustomEditors();
    document.getElementById('calc-retailer-notes').value = customRetailer.notes ?? '';
  } else {
    const r = retailerById(rid);
    if (!r) { editor.style.display = 'none'; notesWrap.style.display = 'none'; return; }
    document.getElementById('ie-maxh').value       = r.max_height;
    document.getElementById('ie-pallets').value    = r.max_pallets_per_floor ?? 26;
    document.getElementById('ie-ds').checked       = r.double_stack_allowed;
    document.getElementById('ie-nopallet').checked = r.no_pallet ?? false;
    document.getElementById('calc-retailer-notes').value = r.notes ?? '';
  }
  editor.style.display = 'block';
  notesWrap.style.display = 'block';
}

function updateClubPanel() {
  const rid = document.getElementById('retailer-select').value;
  const r = rid === 'custom' ? null : retailerById(rid);
  const isClub = r && r.is_club_store;
  document.getElementById('club-display-panel').style.display = isClub ? '' : 'none';
  if (!isClub) {
    document.getElementById('shoppable-metrics-row').style.display = 'none';
    document.getElementById('shoppable-error-banner').style.display = 'none';
  }

  const fillInput = document.getElementById('club-fill-chimney');
  const fillLabel = document.getElementById('club-fill-label');
  if (isClub && r && !r.chimney_allowed) {
    fillInput.checked = true;
    fillInput.disabled = true;
    fillLabel.classList.add('toggle-label--disabled');
    fillLabel.title = `${r.name} does not permit open chimneys`;
  } else {
    fillInput.disabled = false;
    fillLabel.classList.remove('toggle-label--disabled');
    fillLabel.title = '';
  }

  if (isClub && r) {
    const DEFAULTS = { "BJ's Wholesale": 2 };
    const defaultSides = DEFAULTS[r.name] || 4;
    document.querySelectorAll('#side-selector .side-btn').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.sides) === defaultSides);
    });
  }
}

function setupSideSelector() {
  document.querySelectorAll('#side-selector .side-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('#side-selector .side-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

function getShoppableParams() {
  const panel = document.getElementById('club-display-panel');
  if (!panel || panel.style.display === 'none') return null;

  const activeBtn = document.querySelector('#side-selector .side-btn.active');
  const sides = activeBtn ? parseInt(activeBtn.dataset.sides) : 4;
  if (sides === 0) return null;

  return {
    sides,
    max_empty_pct: (parseFloat(document.getElementById('club-max-empty').value) || 15) / 100,
    min_footprint: [
      parseFloat(document.getElementById('club-fp-w').value) || 37,
      parseFloat(document.getElementById('club-fp-l').value) || 45,
    ],
    force_fill_on_failure: document.getElementById('club-fill-chimney').checked,
  };
}

function renderShoppableResults(s) {
  const banner = document.getElementById('shoppable-error-banner');
  const row    = document.getElementById('shoppable-metrics-row');

  if (!s) {
    banner.style.display = 'none';
    row.style.display = 'none';
    return;
  }

  banner.style.display = 'none';

  document.getElementById('val-shoppable-ti').textContent = s.ti;
  document.getElementById('val-shoppable-void').textContent = pct(s.void_pct);

  row.style.display = '';
}

function refreshBulkRetailerInfo() {
  const rid       = document.getElementById('bulk-retailer').value;
  const editor    = document.getElementById('bulk-custom-editor');
  const notesWrap = document.getElementById('bulk-notes-wrap');
  const isCustom  = rid === 'custom';
  if (!rid) { editor.style.display = 'none'; notesWrap.style.display = 'none'; return; }

  editor.querySelector('.panel-label').textContent = isCustom ? 'CUSTOM RETAILER' : 'RETAILER DETAILS';
  ['bulk-ie-maxh', 'bulk-ie-pallets', 'bulk-ie-ds', 'bulk-ie-nopallet'].forEach(id => {
    document.getElementById(id).disabled = !isCustom;
  });

  if (isCustom) {
    syncCustomEditors();
    document.getElementById('bulk-retailer-notes').value = customRetailer.notes ?? '';
  } else {
    const r = retailerById(rid);
    if (!r) { editor.style.display = 'none'; notesWrap.style.display = 'none'; return; }
    document.getElementById('bulk-ie-maxh').value        = r.max_height;
    document.getElementById('bulk-ie-pallets').value     = r.max_pallets_per_floor ?? 26;
    document.getElementById('bulk-ie-ds').checked        = r.double_stack_allowed;
    document.getElementById('bulk-ie-nopallet').checked  = r.no_pallet ?? false;
    document.getElementById('bulk-retailer-notes').value = r.notes ?? '';
  }
  editor.style.display = 'block';
  notesWrap.style.display = 'block';
}

async function saveRetailerNotes(fieldId, selectId) {
  const rid   = document.getElementById(selectId).value;
  const notes = document.getElementById(fieldId).value;
  if (!rid) return;
  if (rid === 'custom') {
    customRetailer.notes = notes;
    saveCustomRetailer();
    return;
  }
  try {
    const res = await fetch(API.retailerNotes(rid), {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ notes }),
    });
    if (res.ok) {
      const r = retailerById(rid);
      if (r) r.notes = notes;
      showToast('Notes saved');
    }
  } catch (e) { console.error(e); }
}

async function doCalculate() {
  const l  = parseFloat(document.getElementById('c-l').value);
  const w  = parseFloat(document.getElementById('c-w').value);
  const h  = parseFloat(document.getElementById('c-h').value);
  const cp  = Math.max(1, parseInt(document.getElementById('c-cp').value, 10) || 1);
  const rid = document.getElementById('retailer-select').value;

  if (!rid)                        { flashBtn('SELECT RETAILER'); return; }
  if (!l || !w || !h || l<=0 || w<=0 || h<=0) { flashBtn('CHECK DIMENSIONS'); return; }

  setBtnState('calc-btn', 'calc-btn-text', 'CALCULATING…', true);
  setStatus('Calculating…');

  try {
    const body = { length: l, width: w, height: h, retailer_id: rid, case_pack_qty: cp };
    if (rid === 'custom') Object.assign(body, customRetailer);
    const shoppable = getShoppableParams();
    if (shoppable) body.shoppable = shoppable;
    const res  = await fetch(API.calculate, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok) { flashBtn(data.error || 'ERROR'); setStatus(data.error || 'Error', true); return; }
    renderResults(data);
    setStatus('Ready');
  } catch (e) {
    flashBtn('CONN ERROR');
    setStatus('Connection error', true);
  } finally {
    setBtnState('calc-btn', 'calc-btn-text', 'CALCULATE', false);
  }
}

function renderResults(d) {
  lastResult = d;

  setMetric('val-ti',    d.ti,    'mc-ti');
  setMetric('val-hi',    d.hi,    'mc-hi');
  setMetric('val-total', d.total, 'mc-total');
  setMetric('val-upp',   d.case_pack_qty * d.total, 'mc-upp');

  // Truckload
  setMetric('val-tl', d.truckload_qty.toLocaleString(), 'mc-tl');
  const fmParts = [d.case_pack_qty, d.total, d.max_pallets_per_floor];
  if (d.stack_multiplier > 1) fmParts.push(d.stack_multiplier);
  document.getElementById('tl-formula').textContent =
    fmParts.join(' × ') + ' = ' + d.truckload_qty.toLocaleString() + ' units';

  const _rid = document.getElementById('retailer-select').value;
  const r = _rid === 'custom' ? { ...customRetailer, name: 'Custom' } : retailerById(_rid);
  document.getElementById('results-meta').textContent =
    r ? `${r.max_pallets_per_floor} pallets · ${r.name}` : '';

  const caseWeight = parseFloat(document.getElementById('c-cw').value) || 0;
  const palletWeight    = caseWeight * d.total;
  const truckloadWeight = caseWeight * d.total * d.max_pallets_per_floor * d.stack_multiplier;

  document.getElementById('detail-strip').style.display = 'grid';
  document.getElementById('d-pallet-wt').textContent   = formatWeight(palletWeight);
  document.getElementById('d-efficiency').textContent  = pct(d.efficiency);
  document.getElementById('d-height').textContent =
    `${d.pod_height}"${r?.no_pallet ? ' · no pallet' : ''}`;
  document.getElementById('d-pod-l').textContent  = d.pod_length ? `${d.pod_length}"` : '—';
  document.getElementById('d-pod-w').textContent  = d.pod_width  ? `${d.pod_width}"` : '—';
  document.getElementById('d-tl-wt').textContent  = formatWeight(truckloadWeight);

  drawDiagram(d);
  renderShoppableResults(d.shoppable || null);
}

function setMetric(valId, value, cardId) {
  const el = document.getElementById(valId);
  el.classList.remove('pop');
  void el.offsetWidth;
  el.textContent = value;
  el.classList.add('pop');
  document.getElementById(cardId).classList.add('lit');
}

// ── SVG Diagram ──────────────────────────────────────────────
function drawDiagram(d) {
  const box = document.getElementById('diagram-box');
  if (!d) return;

  if (d.shoppable && d.shoppable.arrangement && d.shoppable.arrangement.length > 0) {
    drawShoppableView(d, box);
    return;
  }

  if (diagramView === 'hi') {
    drawStackedView(d, box);
  } else {
    drawTiView(d, box);
  }
}

function drawTiView(d, box) {
  const { pallet_length: PL, pallet_width: PW, arrangement } = d;

  if (!arrangement || !arrangement.length) {
    box.innerHTML = '<div class="diagram-empty"><svg viewBox="0 0 200 300" fill="none"><text x="100" y="150" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="9" fill="#3d5068">no arrangement data</text></svg></div>';
    return;
  }

  const VW = 580, VH = 480;
  const PAD = 32;
  const LEGEND_H = 22;

  const scale = Math.min((VW - PAD * 2) / PL, (VH - PAD * 2 - LEGEND_H) / PW);
  const dW    = PL * scale;
  const dH    = PW * scale;
  const ox    = (VW - dW) / 2;
  const oy    = PAD + ((VH - PAD * 2 - LEGEND_H) - dH) / 2;

  const gPitch = Math.max(4, Math.round(20 / scale)) * scale;

  let svg = `<svg viewBox="0 0 ${VW} ${VH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;display:block">
<defs>
  <pattern id="g" x="${ox}" y="${oy}" width="${gPitch}" height="${gPitch}" patternUnits="userSpaceOnUse">
    <path d="M ${gPitch} 0 L 0 0 0 ${gPitch}" fill="none" stroke="#253047" stroke-width="0.5"/>
  </pattern>
  <clipPath id="pal-clip">
    <rect x="${ox}" y="${oy}" width="${dW}" height="${dH}"/>
  </clipPath>
</defs>`;

  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="#0d1119"/>`;
  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="url(#g)"/>`;

  arrangement.forEach(c => {
    const cx = ox + c.x * scale;
    const cy = oy + c.y * scale;
    const cw = c.w * scale;
    const ch = c.h * scale;
    const fill   = c.rotated ? 'rgba(200,240,160,.13)' : 'rgba(255,212,184,.13)';
    const stroke = c.rotated ? '#C8F0A0' : '#FFD4B8';

    svg += `<rect x="${(cx+.8).toFixed(1)}" y="${(cy+.8).toFixed(1)}" `
         + `width="${Math.max(0,cw-1.6).toFixed(1)}" height="${Math.max(0,ch-1.6).toFixed(1)}" `
         + `fill="${fill}" stroke="${stroke}" stroke-width="0.7" clip-path="url(#pal-clip)"/>`;

    if (cw > 14 && ch > 14) {
      const mx = (cx + cw / 2).toFixed(1);
      const my = (cy + ch / 2).toFixed(1);
      svg += `<line x1="${mx}" y1="${(cy+ch/2-4).toFixed(1)}" x2="${mx}" y2="${(cy+ch/2+4).toFixed(1)}" stroke="${stroke}" stroke-width="0.5" opacity="0.4" clip-path="url(#pal-clip)"/>`;
      svg += `<line x1="${(cx+cw/2-4).toFixed(1)}" y1="${my}" x2="${(cx+cw/2+4).toFixed(1)}" y2="${my}" stroke="${stroke}" stroke-width="0.5" opacity="0.4" clip-path="url(#pal-clip)"/>`;
    }
  });

  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="none" stroke="#334060" stroke-width="1.5"/>`;

  const annotColor = '#3d5068';
  const af = 'font-family="JetBrains Mono,monospace"';
  svg += `<text x="${(ox+dW/2).toFixed(1)}" y="${(oy-7).toFixed(1)}" text-anchor="middle" ${af} font-size="9" fill="${annotColor}">${PL}"</text>`;
  svg += `<text x="${(ox-9).toFixed(1)}" y="${(oy+dH/2).toFixed(1)}" text-anchor="middle" ${af} font-size="9" fill="${annotColor}" `
       + `transform="rotate(-90,${(ox-9).toFixed(1)},${(oy+dH/2).toFixed(1)})">${PW}"</text>`;

  const ly = (oy + dH + 12).toFixed(1);
  svg += `<rect x="${ox}" y="${ly}" width="8" height="8" fill="rgba(255,212,184,.13)" stroke="#f5c4be" stroke-width="0.7"/>`;
  svg += `<text x="${(ox+12).toFixed(1)}" y="${(parseFloat(ly)+7).toFixed(1)}" ${af} font-size="8" fill="#7a8faa">Standard</text>`;
  svg += `<rect x="${(ox+76).toFixed(1)}" y="${ly}" width="8" height="8" fill="rgba(200,240,160,.13)" stroke="#d2eca4" stroke-width="0.7"/>`;
  svg += `<text x="${(ox+88).toFixed(1)}" y="${(parseFloat(ly)+7).toFixed(1)}" ${af} font-size="8" fill="#7a8faa">Rotated 90°</text>`;

  svg += '</svg>';
  box.innerHTML = svg;
}

function drawStackedView(d, box) {
  const { pallet_length: PL, pallet_width: PW, arrangement, hi, case_h: CH } = d;

  if (!arrangement || !arrangement.length || !hi || !CH) {
    const msg = hi === 0 ? 'Hi = 0 (case too tall)' : 'no stacked data';
    box.innerHTML = `<div class="diagram-empty"><svg viewBox="0 0 200 300" fill="none"><text x="100" y="150" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="9" fill="#3d5068">${msg}</text></svg></div>`;
    return;
  }

  const VW = 290, VH = 460;
  const PAD = 18;
  const LEGEND_H = 18;
  const EXTRA_TOP = 10;

  const COS30 = Math.cos(Math.PI / 6);
  const SIN30 = 0.5;

  // Scale to fit diamond footprint horizontally
  const hScale = (VW - 2 * PAD) / ((PL + PW) * COS30);

  // Floor height in screen px
  const floorH_screen = (PL + PW) * SIN30 * hScale;

  // Scale height so stack fits vertically; cap to keep boxes looking natural
  const stackWorldH = hi * CH;
  const availForStack = VH - 2 * PAD - EXTRA_TOP - LEGEND_H - floorH_screen;
  const rawVScale = availForStack > 0 ? availForStack / stackWorldH : hScale;
  const vScale = Math.min(rawVScale, hScale * 3.5);

  // Vertically center content when vScale is capped
  const stackH_screen = stackWorldH * vScale;
  const totalContentH = stackH_screen + floorH_screen;
  const freeV = Math.max(0, (VH - 2 * PAD - EXTRA_TOP - LEGEND_H) - totalContentH);

  // World (0,0,0) origin in SVG coords
  const originX = PAD + PW * COS30 * hScale;
  const originY = PAD + EXTRA_TOP + freeV / 2 + stackH_screen;

  function iso(wx, wy, wz) {
    return {
      x: originX + (wx - wy) * COS30 * hScale,
      y: originY + (wx + wy) * SIN30 * hScale - wz * vScale,
    };
  }

  function poly(pts, fill, stroke, sw) {
    const s = pts.map(p => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');
    return `<polygon points="${s}" fill="${fill}" stroke="${stroke}" stroke-width="${sw}"/>`;
  }

  let svg = `<svg viewBox="0 0 ${VW} ${VH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;display:block">`;

  // Pallet floor diamond
  const f = [iso(0,0,0), iso(PL,0,0), iso(PL,PW,0), iso(0,PW,0)];
  svg += poly(f, '#0b0f18', '#253047', 1);

  // Grid lines on pallet floor (every ~12 world units)
  const gridStep = PL >= 36 ? 12 : 6;
  for (let gx = 0; gx <= PL; gx += gridStep) {
    const a = iso(gx, 0, 0), b = iso(gx, PW, 0);
    svg += `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="#1e2d40" stroke-width="0.5"/>`;
  }
  for (let gy = 0; gy <= PW; gy += gridStep) {
    const a = iso(0, gy, 0), b = iso(PL, gy, 0);
    svg += `<line x1="${a.x.toFixed(1)}" y1="${a.y.toFixed(1)}" x2="${b.x.toFixed(1)}" y2="${b.y.toFixed(1)}" stroke="#1e2d40" stroke-width="0.5"/>`;
  }

  const zFull = hi * CH;

  // BFS from the far-back corner case outward toward the viewer.
  // Two cases are adjacent when their footprints share an edge (within EPS).
  const cDepth = c => c.x + c.w / 2 + c.y + c.h / 2;
  const EPS = 0.01;
  const adjoin = (a, b) => {
    const xTch = Math.abs(a.x + a.w - b.x) < EPS || Math.abs(b.x + b.w - a.x) < EPS;
    const yOvr = a.y < b.y + b.h - EPS && b.y < a.y + a.h - EPS;
    const yTch = Math.abs(a.y + a.h - b.y) < EPS || Math.abs(b.y + b.h - a.y) < EPS;
    const xOvr = a.x < b.x + b.w - EPS && b.x < a.x + a.w - EPS;
    return (xTch && yOvr) || (yTch && xOvr);
  };
  const cKey  = c => `${c.x.toFixed(1)},${c.y.toFixed(1)}`;
  const start = arrangement.reduce((best, c) => cDepth(c) < cDepth(best) ? c : best);
  const visited = new Set([cKey(start)]);
  const bfsOrder = [];
  const queue = [start];
  while (queue.length) {
    const curr = queue.shift();
    bfsOrder.push(curr);
    for (const c of arrangement) {
      const k = cKey(c);
      if (!visited.has(k) && adjoin(curr, c)) { visited.add(k); queue.push(c); }
    }
  }
  // Any cases unreachable (disconnected edge case)
  arrangement.forEach(c => { if (!visited.has(cKey(c))) bfsOrder.push(c); });

  // For each case column in BFS order: paint right wall → front wall →
  // layer dividers → bottom cap. Near columns drawn later overwrite far ones.
  bfsOrder.forEach(c => {
    const { x: cx, y: cy, w: cw, h: cdp, rotated } = c;
    const base = rotated ? [200, 240, 160] : [255, 212, 184];

    const bottomFill   = `rgb(${base.map(v => Math.round(v * 0.88)).join(',')})`;
    const rightFill = `rgb(${base.map(v => Math.round(v * 0.52)).join(',')})`;
    const frontFill = `rgb(${base.map(v => Math.round(v * 0.38)).join(',')})`;
    const edge      = 'rgba(0,0,0,0.55)';
    const divider   = 'rgba(0,0,0,0.50)';

    // 1. Full-height right face (+x wall)
    svg += poly(
      [iso(cx+cw,cy,zFull), iso(cx+cw,cy+cdp,zFull), iso(cx+cw,cy+cdp,0), iso(cx+cw,cy,0)],
      rightFill, edge, 0.7
    );

    // 2. Full-height front face (near-y wall, closest to viewer)
    svg += poly(
      [iso(cx,cy,0), iso(cx+cw,cy,0), iso(cx+cw,cy,zFull), iso(cx,cy,zFull)],
      frontFill, edge, 0.7
    );

    // 3. Horizontal layer divider lines drawn on top of the solid faces
    for (let k = 1; k < hi; k++) {
      const z = k * CH;
      const ra = iso(cx+cw, cy, z),      rb = iso(cx+cw, cy+cdp, z);
      const fa = iso(cx, cy, z),          fb = iso(cx+cw, cy, z);
      svg += `<line x1="${ra.x.toFixed(1)}" y1="${ra.y.toFixed(1)}" x2="${rb.x.toFixed(1)}" y2="${rb.y.toFixed(1)}" stroke="${divider}" stroke-width="0.9"/>`;
      svg += `<line x1="${fa.x.toFixed(1)}" y1="${fa.y.toFixed(1)}" x2="${fb.x.toFixed(1)}" y2="${fb.y.toFixed(1)}" stroke="${divider}" stroke-width="0.9"/>`;
    }

    // 4. Top face (drawn last = caps the prism and overwrites any side-face artifacts)
    svg += poly(
      [iso(cx,cy,zFull), iso(cx+cw,cy,zFull), iso(cx+cw,cy+cdp,zFull), iso(cx,cy+cdp,zFull)],
      bottomFill, edge, 0.7
    );
  });

  // Pallet border re-draw over everything
  svg += poly(f, 'none', '#334060', 1.5);

  // Layer count badge (bottom of stack, front-left corner)
  if (hi > 0) {
    const bottomPt = iso(0, 0, hi * CH);
    svg += `<text x="${bottomPt.x.toFixed(1)}" y="${(bottomPt.y - 5).toFixed(1)}" font-family="JetBrains Mono,monospace" font-size="9" fill="#7a95b0" text-anchor="middle">Hi=${hi}</text>`;
  }

  // Legend
  const af = 'font-family="JetBrains Mono,monospace"';
  const ly = (VH - LEGEND_H + 2).toFixed(1);
  svg += `<rect x="10" y="${ly}" width="8" height="8" fill="rgba(255,212,184,0.3)" stroke="#f5c4be" stroke-width="0.7"/>`;
  svg += `<text x="22" y="${(parseFloat(ly)+7).toFixed(1)}" ${af} font-size="8" fill="#7a8faa">Standard</text>`;
  svg += `<rect x="82" y="${ly}" width="8" height="8" fill="rgba(200,240,160,0.3)" stroke="#d2eca4" stroke-width="0.7"/>`;
  svg += `<text x="94" y="${(parseFloat(ly)+7).toFixed(1)}" ${af} font-size="8" fill="#7a8faa">Rotated</text>`;

  svg += '</svg>';
  box.innerHTML = svg;
}

function drawShoppableView(d, box) {
  const { pallet_length: PL, pallet_width: PW } = d;
  const positions = d.shoppable.arrangement;

  if (!positions || !positions.length) {
    box.innerHTML = '<div class="diagram-empty"><svg viewBox="0 0 200 300" fill="none"><text x="100" y="150" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="9" fill="#3d5068">no arrangement data</text></svg></div>';
    return;
  }

  const VW = 580, VH = 480;
  const PAD = 32;
  const LEGEND_H = 22;

  // Rotated 90°: PL (depth) runs horizontally, PW (front face) runs vertically.
  // Case coords transform: rx = PL - c.y - c.h,  ry = c.x,  rw = c.h,  rh = c.w
  const scale = Math.min((VW - PAD * 2) / PL, (VH - PAD * 2 - LEGEND_H) / PW);
  const dW = PL * scale;
  const dH = PW * scale;
  const ox = (VW - dW) / 2;
  const oy = PAD + ((VH - PAD * 2 - LEGEND_H) - dH) / 2;

  const SIDE_STROKE = { top: '#a78bfa', right: '#67e8f9', bottom: '#86efac', left: '#fbbf24' };
  const SIDE_FILL   = { top: 'rgba(167,139,250,.20)', right: 'rgba(103,232,249,.20)', bottom: 'rgba(134,239,172,.20)', left: 'rgba(251,191,36,.20)' };

  const stroke = (side) => SIDE_STROKE[side] || '#a78bfa';
  const fill   = (side) => SIDE_FILL[side]   || 'rgba(167,139,250,.20)';

  const gPitch = Math.max(4, Math.round(20 / scale)) * scale;
  let svg = `<svg viewBox="0 0 ${VW} ${VH}" xmlns="http://www.w3.org/2000/svg" style="width:100%;height:100%;display:block">
<defs>
  <pattern id="g" x="${ox}" y="${oy}" width="${gPitch}" height="${gPitch}" patternUnits="userSpaceOnUse">
    <path d="M ${gPitch} 0 L 0 0 0 ${gPitch}" fill="none" stroke="#253047" stroke-width="0.5"/>
  </pattern>
  <clipPath id="pal-clip"><rect x="${ox}" y="${oy}" width="${dW}" height="${dH}"/></clipPath>
</defs>`;

  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="#0d1119"/>`;
  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="url(#g)"/>`;

  positions.forEach(c => {
    const cx = ox + (PL - c.y - c.h) * scale;
    const cy = oy + c.x * scale;
    const cw = c.h * scale;
    const ch = c.w * scale;
    svg += `<rect x="${(cx + .8).toFixed(1)}" y="${(cy + .8).toFixed(1)}" `
         + `width="${Math.max(0, cw - 1.6).toFixed(1)}" height="${Math.max(0, ch - 1.6).toFixed(1)}" `
         + `fill="${fill(c.side)}" stroke="${stroke(c.side)}" stroke-width="0.7" clip-path="url(#pal-clip)"/>`;
  });

  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="none" stroke="#334060" stroke-width="1.5"/>`;

  const af = 'font-family="JetBrains Mono,monospace"';
  const ac = '#3d5068';
  svg += `<text x="${(ox + dW / 2).toFixed(1)}" y="${(oy - 7).toFixed(1)}" text-anchor="middle" ${af} font-size="9" fill="${ac}">${PL}" (depth)</text>`;
  svg += `<text x="${(ox - 9).toFixed(1)}" y="${(oy + dH / 2).toFixed(1)}" text-anchor="middle" ${af} font-size="9" fill="${ac}" transform="rotate(-90,${(ox - 9).toFixed(1)},${(oy + dH / 2).toFixed(1)})">${PW}" (front face)</text>`;

  const ly = (oy + dH + 12).toFixed(1);
  let lx = ox;
  const presentSides = [...new Set(positions.map(p => p.side))].filter(s => SIDE_STROKE[s]);
  presentSides.forEach(side => {
    svg += `<rect x="${lx.toFixed(1)}" y="${ly}" width="8" height="8" fill="${fill(side)}" stroke="${stroke(side)}" stroke-width="0.7"/>`;
    svg += `<text x="${(lx + 12).toFixed(1)}" y="${(parseFloat(ly) + 7).toFixed(1)}" ${af} font-size="8" fill="#7a8faa">${side}</text>`;
    lx += 52;
  });

  svg += '</svg>';
  box.innerHTML = svg;
}

// ── Bulk Diagram Modal ───────────────────────────────────────
function openBulkDiagram(idx) {
  const row = bulkResults[idx];
  if (!row || !row.arrangement) return;
  document.getElementById('bulk-diagram-title').textContent = row.sku || `ROW ${idx + 1}`;
  document.getElementById('bulk-diagram-hint').textContent =
    `top-down · 1 layer · Ti = ${row.ti} · ${row.arrangement_desc || ''}`;
  const modal = document.getElementById('bulk-diagram-modal');
  modal.style.display = 'flex';
  drawTiView(row, document.getElementById('bulk-diagram-box'));
}

function closeBulkDiagram() {
  document.getElementById('bulk-diagram-modal').style.display = 'none';
}

// ── Bulk Import ──────────────────────────────────────────────
function setupBulk() {
  const drop  = document.getElementById('drop-zone');
  const input = document.getElementById('file-input');

  drop.addEventListener('click', e => {
    if (e.target.closest('label') || e.target === input) return;
    input.click();
  });
  drop.addEventListener('dragover',  e  => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', ()  => drop.classList.remove('over'));
  drop.addEventListener('drop',      e  => {
    e.preventDefault(); drop.classList.remove('over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => { if (input.files[0]) handleFile(input.files[0]); });

  document.getElementById('bulk-calc-btn').addEventListener('click', doBulkCalc);
  document.getElementById('export-btn').addEventListener('click', exportResults);

  document.getElementById('bulk-retailer').addEventListener('change', refreshBulkRetailerInfo);

  const debouncedBulkNotes = debounce(() => saveRetailerNotes('bulk-retailer-notes', 'bulk-retailer'), 800);
  document.getElementById('bulk-retailer-notes').addEventListener('input', debouncedBulkNotes);
  document.getElementById('bulk-retailer-notes').addEventListener('blur', () => saveRetailerNotes('bulk-retailer-notes', 'bulk-retailer'));

  const debouncedBulkIE = debounce(() => readCustomEditorValues('bulk-ie'), 500);
  ['bulk-ie-maxh', 'bulk-ie-pallets'].forEach(id => {
    document.getElementById(id).addEventListener('input', debouncedBulkIE);
    document.getElementById(id).addEventListener('blur', () => readCustomEditorValues('bulk-ie'));
  });
  document.getElementById('bulk-ie-ds').addEventListener('change', () => readCustomEditorValues('bulk-ie'));
  document.getElementById('bulk-ie-nopallet').addEventListener('change', () => readCustomEditorValues('bulk-ie'));

  document.getElementById('bulk-diagram-close').addEventListener('click', closeBulkDiagram);
  document.getElementById('bulk-diagram-modal').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeBulkDiagram();
  });

  document.getElementById('dl-template').addEventListener('click', e => {
    e.preventDefault();
    const csv = 'sku,length,width,height,case_weight,case_pack_qty\nITEM-001,12,8,6,18.5,4\nITEM-002,10,10,8,12.0,1\nITEM-003,14,6,5,9.75,2\n';
    dlString(csv, 'pallet-town-template.csv', 'text/csv');
  });
}

function handleFile(file) {
  const reader = new FileReader();
  reader.onload = e => {
    bulkData = parseCSV(e.target.result, file.name);
    if (bulkData.length) {
      setBulkStatus(`${bulkData.length} case${bulkData.length !== 1 ? 's' : ''} loaded from ${file.name}`);
      document.getElementById('bulk-calc-btn').disabled = false;
    }
  };
  reader.readAsText(file);
}

function parseCSV(text, filename) {
  const lines = text.trim().split(/\r?\n/);
  if (lines.length < 2) { setBulkStatus('CSV is empty or has only headers.', true); return []; }

  const headers = lines[0].toLowerCase().split(',').map(s => s.trim());
  const idx = name => headers.findIndex(h => h.includes(name));
  const si = idx('sku'), li = idx('len'), wi = idx('wid'), hi = idx('hei'), cpi = idx('pack'), cwi = idx('weight');

  if (li === -1 || wi === -1 || hi === -1) {
    setBulkStatus('CSV needs length, width, height columns.', true);
    return [];
  }

  const rows = lines.slice(1).map((line, i) => {
    const cols = line.split(',').map(s => s.trim());
    const l = parseFloat(cols[li]), w = parseFloat(cols[wi]), h = parseFloat(cols[hi]);
    if (!l || !w || !h || l <= 0 || w <= 0 || h <= 0) return null;
    const row = {
      sku: si >= 0 ? cols[si] : `ROW-${i + 1}`,
      length: l, width: w, height: h,
    };
    if (cpi >= 0 && cols[cpi]) {
      const cp = parseInt(cols[cpi], 10);
      if (cp >= 1) row.case_pack_qty = cp;
    }
    if (cwi >= 0 && cols[cwi]) {
      const cw = parseFloat(cols[cwi]);
      if (cw > 0) row.case_weight = cw;
    }
    return row;
  }).filter(Boolean);

  if (!rows.length) { setBulkStatus('No valid rows found.', true); return []; }
  return rows;
}

async function doBulkCalc() {
  const rid = document.getElementById('bulk-retailer').value;
  const cp  = Math.max(1, parseInt(document.getElementById('bulk-cp').value, 10) || 1);

  if (!rid)              { setBulkStatus('Select a retailer.', true); return; }
  if (!bulkData.length)  { setBulkStatus('Upload a CSV first.', true); return; }

  setBtnState('bulk-calc-btn', 'bulk-btn-text', 'CALCULATING…', true);
  setBulkStatus(`Processing ${bulkData.length} cases…`);

  try {
    const body = { cases: bulkData, retailer_id: rid, case_pack_qty: cp };
    if (rid === 'custom') Object.assign(body, customRetailer);
    const res  = await fetch(API.bulkCalc, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    bulkResults = await res.json();
    if (!res.ok) { setBulkStatus(bulkResults.error || 'Error', true); return; }
    const defaultCaseWeight = parseFloat(document.getElementById('bulk-cw').value) || 0;
    bulkResults.forEach((r, i) => {
      const cw = (bulkData[i] && bulkData[i].case_weight) || defaultCaseWeight;
      r.case_weight      = cw;
      r.pallet_weight    = cw * r.total;
      r.truckload_weight = cw * r.total * r.max_pallets_per_floor * r.stack_multiplier;
    });
    renderBulkTable(bulkResults);
    setBulkStatus(`${bulkResults.length} cases calculated.`);
  } catch {
    setBulkStatus('Connection error.', true);
  } finally {
    setBtnState('bulk-calc-btn', 'bulk-btn-text', 'CALCULATE ALL', false);
  }
}

function renderBulkTable(rows) {
  const panel = document.getElementById('bulk-results');
  panel.style.display = 'flex';

  const tbody = document.getElementById('table-body');
  tbody.innerHTML = rows.map((r, i) => {
    const e = Math.round(r.efficiency * 100);
    const cls = e >= 80 ? 'hi' : e >= 60 ? 'mid' : 'lo';
    return `<tr>
      <td>${esc(r.sku)}</td>
      <td>${r.length}" × ${r.width}" × ${r.height}"</td>
      <td>${formatWeight(r.case_weight)}</td>
      <td>${r.case_pack_qty}</td>
      <td class="td-ti">${r.ti}</td>
      <td class="td-hi">${r.hi}</td>
      <td class="td-total">${r.total}</td>
      <td>${r.case_pack_qty * r.total}</td>
      <td>${formatWeight(r.pallet_weight)}</td>
      <td class="td-tl">${r.truckload_qty.toLocaleString()}</td>
      <td>${formatWeight(r.truckload_weight)}</td>
      <td>${r.pod_length}" × ${r.pod_width}" × ${r.pod_height}"</td>
      <td><span class="eff-badge ${cls}">${e}%</span></td>
      <td><button class="view-btn" data-idx="${i}">VIEW</button></td>
    </tr>`;
  }).join('');

  tbody.querySelectorAll('.view-btn').forEach(btn =>
    btn.addEventListener('click', () => openBulkDiagram(parseInt(btn.dataset.idx, 10)))
  );
}

function exportResults() {
  if (!bulkResults.length) return;
  const head = 'SKU,Length,Width,Height,Case Weight (lbs),Case Pack Qty,Ti,Hi,Cases Per Pallet,Units Per Pallet,Pallet Wt (lbs),Units Per Truckload,Truckload Weight (lbs),Pod Length,Pod Width,Pod Height,Efficiency\n';
  const body = bulkResults.map(r =>
    `${r.sku},${r.length},${r.width},${r.height},${r.case_weight || 0},${r.case_pack_qty},${r.ti},${r.hi},${r.total},${r.case_pack_qty * r.total},${r.pallet_weight || 0},${r.truckload_qty},${r.truckload_weight || 0},${r.pod_length},${r.pod_width},${r.pod_height},${Math.round(r.efficiency * 100)}%`
  ).join('\n');
  dlString(head + body, 'pallet-results.csv', 'text/csv');
}

// ── Retailers tab ────────────────────────────────────────────
let selectedRetailerId = null;

function setupRetailersTab() {
  document.getElementById('add-retailer-btn').addEventListener('click', addRetailer);
  document.getElementById('rd-delete').addEventListener('click', () => {
    if (selectedRetailerId) deleteRetailer(selectedRetailerId);
  });

  const save = () => { if (selectedRetailerId) saveDetailRetailer(); };
  const debouncedSave = debounce(save, 800);
  ['rd-name', 'rd-maxh', 'rd-pallets', 'rd-notes'].forEach(id => {
    document.getElementById(id).addEventListener('input', debouncedSave);
    document.getElementById(id).addEventListener('blur', save);
  });
  ['rd-ds', 'rd-np'].forEach(id => {
    document.getElementById(id).addEventListener('change', save);
  });
}

function renderRetailersGrid() {
  const list = document.getElementById('retailers-list');
  list.innerHTML = retailers.map(r =>
    `<div class="r-list-item${String(r.id) === String(selectedRetailerId) ? ' active' : ''}"
          data-id="${r.id}">${esc(r.name)}</div>`
  ).join('');
  list.querySelectorAll('.r-list-item').forEach(item =>
    item.addEventListener('click', () => selectRetailer(item.dataset.id))
  );
  updateAuthUI();
  if (selectedRetailerId) {
    const r = retailerById(selectedRetailerId);
    r ? renderRetailerDetail(r) : showDetailEmpty();
  }
}

function selectRetailer(id) {
  selectedRetailerId = String(id);
  document.querySelectorAll('.r-list-item').forEach(item =>
    item.classList.toggle('active', String(item.dataset.id) === String(id))
  );
  const r = retailerById(id);
  if (r) renderRetailerDetail(r);
}

function renderRetailerDetail(r) {
  document.getElementById('r-detail-empty').style.display   = 'none';
  document.getElementById('r-detail-content').style.display = 'block';
  document.getElementById('rd-name').value    = r.name;
  document.getElementById('rd-maxh').value    = r.max_height;
  document.getElementById('rd-pallets').value = r.max_pallets_per_floor ?? 26;
  document.getElementById('rd-ds').checked    = r.double_stack_allowed;
  document.getElementById('rd-np').checked    = r.no_pallet ?? false;
  document.getElementById('rd-notes').value   = r.notes ?? '';
  updateAuthUI();
}

function showDetailEmpty() {
  document.getElementById('r-detail-empty').style.display   = 'flex';
  document.getElementById('r-detail-content').style.display = 'none';
}

async function saveDetailRetailer() {
  if (!isAdmin || !selectedRetailerId) return;
  const payload = {
    name:                  document.getElementById('rd-name').value.trim(),
    max_height:            parseFloat(document.getElementById('rd-maxh').value),
    max_pallets_per_floor: parseInt(document.getElementById('rd-pallets').value, 10),
    double_stack_allowed:  document.getElementById('rd-ds').checked,
    no_pallet:             document.getElementById('rd-np').checked,
    notes:                 document.getElementById('rd-notes').value,
  };
  if (!payload.name || isNaN(payload.max_height) || isNaN(payload.max_pallets_per_floor)) return;
  try {
    const res = await fetch(API.retailer(selectedRetailerId), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) {
      const r = retailerById(selectedRetailerId);
      if (r) Object.assign(r, payload);
      const item = document.querySelector(`.r-list-item[data-id="${selectedRetailerId}"]`);
      if (item) item.textContent = payload.name;
      syncRetailerSelects();
      showToast();
    }
  } catch (e) { console.error(e); }
}

async function deleteRetailer(id) {
  if (!confirm('Delete this retailer?')) return;
  try {
    await fetch(API.retailer(id), { method: 'DELETE' });
    selectedRetailerId = null;
    showDetailEmpty();
    await loadRetailers();
  } catch (e) { console.error(e); }
}

async function addRetailer() {
  const name = prompt('New retailer name:');
  if (!name || !name.trim()) return;
  try {
    const res = await fetch(API.retailers, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim(), max_height: 60, double_stack_allowed: false }),
    });
    if (res.ok) {
      const r = await res.json();
      await loadRetailers();
      selectRetailer(r.id);
    }
  } catch (e) { console.error(e); }
}

// ── Utilities ────────────────────────────────────────────────
function setStatus(msg, isErr = false) {
  const el = document.getElementById('status-text');
  el.textContent = msg;
  el.style.color = isErr ? 'var(--red)' : '';
}

function setBulkStatus(msg, isErr = false) {
  const el = document.getElementById('bulk-status');
  el.textContent = msg;
  el.className   = 'bulk-status' + (isErr ? ' err' : '');
}

function setBtnState(btnId, textId, label, disabled) {
  document.getElementById(btnId).disabled   = disabled;
  document.getElementById(textId).textContent = label;
}

function flashBtn(msg) {
  const btn  = document.getElementById('calc-btn');
  const text = document.getElementById('calc-btn-text');
  const orig = text.textContent;
  text.textContent    = msg;
  btn.style.background = 'var(--red)';
  setTimeout(() => { text.textContent = orig; btn.style.background = ''; }, 2000);
}

function pct(fraction) {
  return `${Math.round(fraction * 100)}%`;
}

function formatWeight(lbs) {
  if (!lbs) return '—';
  return lbs.toLocaleString(undefined, { maximumFractionDigits: 0 }) + ' lbs';
}

function esc(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function dlString(content, filename, mime) {
  const a  = document.createElement('a');
  a.href   = URL.createObjectURL(new Blob([content], { type: mime }));
  a.download = filename;
  a.click();
  URL.revokeObjectURL(a.href);
}
