/* ============================================================
   Pallet Town — frontend logic
   ============================================================ */

const API = {
  retailers:      '/api/retailers',
  retailer:  (id) => `/api/retailers/${id}`,
  calculate:      '/api/calculate',
  bulkCalc:       '/api/calculate-bulk',
};

let retailers = [];
let bulkData   = [];
let bulkResults = [];

// ── Bootstrap ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  setupNav();
  await loadRetailers();
  setupCalculator();
  setupBulk();
  setupRetailersTab();
});

// ── Navigation ───────────────────────────────────────────────
function setupNav() {
  const navItems = [...document.querySelectorAll('.nav-item')];
  const TITLES = {
    calculator: 'SINGLE CARTON CALCULATOR',
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
    });
  });
}

// ── Retailers API ────────────────────────────────────────────
async function loadRetailers() {
  try {
    const res = await fetch(API.retailers);
    retailers = await res.json();
    syncRetailerSelects();
    renderRetailersGrid();
  } catch (e) {
    setStatus('Could not load retailers.', true);
  }
}

function syncRetailerSelects() {
  ['retailer-select', 'bulk-retailer'].forEach(id => {
    const sel = document.getElementById(id);
    const cur = sel.value;
    sel.innerHTML = '<option value="">— Select Retailer —</option>';
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
  document.getElementById('retailer-select').addEventListener('change', updateInfoBar);
  document.getElementById('calc-btn').addEventListener('click', doCalculate);
  ['c-l', 'c-w', 'c-h'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => {
      if (e.key === 'Enter') doCalculate();
    });
  });

  // Inline editor: save
  document.getElementById('ie-save-btn').addEventListener('click', async () => {
    const rid = document.getElementById('retailer-select').value;
    if (!rid) return;
    const payload = {
      name:                 document.getElementById('ie-name').value.trim(),
      max_height:           parseFloat(document.getElementById('ie-maxh').value),
      double_stack_allowed: document.getElementById('ie-ds').checked,
    };
    if (!payload.name || isNaN(payload.max_height)) return;
    try {
      const res = await fetch(API.retailer(rid), {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (res.ok) {
        await loadRetailers();
        // Re-select the same retailer after reload
        document.getElementById('retailer-select').value = rid;
        updateInfoBar();
        const btn = document.getElementById('ie-save-btn');
        btn.textContent = 'SAVED';
        btn.classList.add('saved');
        setTimeout(() => { btn.textContent = 'SAVE'; btn.classList.remove('saved'); }, 2000);
      }
    } catch (e) { console.error(e); }
  });

  // Inline editor: collapse toggle
  document.getElementById('ie-toggle').addEventListener('click', () => {
    const body   = document.getElementById('ie-body');
    const toggle = document.getElementById('ie-toggle');
    const collapsed = body.style.display === 'none';
    body.style.display   = collapsed ? 'block' : 'none';
    toggle.textContent   = collapsed ? '▲' : '▼';
  });
}

function updateInfoBar() {
  const r = retailerById(document.getElementById('retailer-select').value);
  const editor = document.getElementById('inline-editor');

  if (!r) {
    document.getElementById('info-maxh').textContent = '—';
    document.getElementById('info-ds').textContent   = '—';
    document.getElementById('info-ds').className     = 'chip-val';
    editor.style.display = 'none';
    return;
  }

  document.getElementById('info-maxh').textContent = `${r.max_height}"`;
  const dsEl = document.getElementById('info-ds');
  if (r.double_stack_allowed) {
    dsEl.textContent = 'Allowed'; dsEl.className = 'chip-val allowed';
    document.getElementById('double-stack').checked = true;
  } else {
    dsEl.textContent = 'No'; dsEl.className = 'chip-val denied';
  }

  // Populate inline editor
  document.getElementById('ie-name').value  = r.name;
  document.getElementById('ie-maxh').value  = r.max_height;
  document.getElementById('ie-ds').checked  = r.double_stack_allowed;
  editor.style.display = 'block';
  document.getElementById('ie-save-btn').classList.remove('saved');
  document.getElementById('ie-save-btn').textContent = 'SAVE';
}

async function doCalculate() {
  const l  = parseFloat(document.getElementById('c-l').value);
  const w  = parseFloat(document.getElementById('c-w').value);
  const h  = parseFloat(document.getElementById('c-h').value);
  const rid = document.getElementById('retailer-select').value;
  const ds  = document.getElementById('double-stack').checked;
  const nop = document.getElementById('no-pallet').checked;

  if (!rid)                        { flashBtn('SELECT RETAILER'); return; }
  if (!l || !w || !h || l<=0 || w<=0 || h<=0) { flashBtn('CHECK DIMENSIONS'); return; }

  setBtnState('calc-btn', 'calc-btn-text', 'CALCULATING…', true);
  setStatus('Calculating…');

  try {
    const res  = await fetch(API.calculate, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ length: l, width: w, height: h, retailer_id: rid,
                             double_stack: ds, exclude_pallet_height: nop }),
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
  setMetric('val-ti',    d.ti,    'mc-ti');
  setMetric('val-hi',    d.hi,    'mc-hi');
  setMetric('val-total', d.total, 'mc-total');

  const r = retailerById(document.getElementById('retailer-select').value);
  document.getElementById('results-meta').textContent =
    r ? `${r.pallet_length}" × ${r.pallet_width}" · ${r.name}` : '';

  document.getElementById('detail-strip').style.display = 'flex';
  document.getElementById('d-pattern').textContent    = d.arrangement_desc || '—';
  document.getElementById('d-efficiency').textContent = pct(d.efficiency);
  const nop = document.getElementById('no-pallet').checked;
  document.getElementById('d-height').textContent =
    `${d.stack_height}"${d.double_stack ? ' (×2 stacked)' : ''}${nop ? ' · no pallet' : ''}`;
  document.getElementById('d-pod-l').textContent = d.pod_length ? `${d.pod_length}"` : '—';
  document.getElementById('d-pod-w').textContent = d.pod_width  ? `${d.pod_width}"` : '—';
  document.getElementById('diagram-hint').textContent =
    `top-down · 1 layer · Ti=${d.ti}`;

  drawDiagram(d);
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
  const { pallet_length: PL, pallet_width: PW, arrangement } = d;

  if (!arrangement || !arrangement.length) {
    box.innerHTML = '<div class="diagram-empty"><svg viewBox="0 0 200 160" fill="none"><text x="100" y="82" text-anchor="middle" font-family="JetBrains Mono,monospace" font-size="9" fill="#3d5068">no arrangement data</text></svg></div>';
    return;
  }

  const VW = 440, VH = 350;
  const PAD = 28;

  const scale = Math.min((VW - PAD * 2) / PL, (VH - PAD * 2) / PW);
  const dW    = PL * scale;
  const dH    = PW * scale;
  const ox    = (VW - dW) / 2;
  const oy    = (VH - dH) / 2;

  // grid pattern pitch — aim for ~20px squares in drawing space
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

  // Pallet floor
  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="#0d1119"/>`;
  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="url(#g)"/>`;

  // Cartons
  arrangement.forEach(c => {
    const cx = ox + c.x * scale;
    const cy = oy + c.y * scale;
    const cw = c.w * scale;
    const ch = c.h * scale;
    const fill   = c.rotated ? 'rgba(52,212,200,.13)' : 'rgba(245,166,35,.13)';
    const stroke = c.rotated ? '#34d4c8' : '#f5a623';

    svg += `<rect x="${(cx+.8).toFixed(1)}" y="${(cy+.8).toFixed(1)}" `
         + `width="${Math.max(0,cw-1.6).toFixed(1)}" height="${Math.max(0,ch-1.6).toFixed(1)}" `
         + `fill="${fill}" stroke="${stroke}" stroke-width="0.7" clip-path="url(#pal-clip)"/>`;

    // Center tick if large enough
    if (cw > 14 && ch > 14) {
      const mx = (cx + cw / 2).toFixed(1);
      const my = (cy + ch / 2).toFixed(1);
      svg += `<line x1="${mx}" y1="${(cy+ch/2-4).toFixed(1)}" x2="${mx}" y2="${(cy+ch/2+4).toFixed(1)}" stroke="${stroke}" stroke-width="0.5" opacity="0.4" clip-path="url(#pal-clip)"/>`;
      svg += `<line x1="${(cx+cw/2-4).toFixed(1)}" y1="${my}" x2="${(cx+cw/2+4).toFixed(1)}" y2="${my}" stroke="${stroke}" stroke-width="0.5" opacity="0.4" clip-path="url(#pal-clip)"/>`;
    }
  });

  // Pallet border overlay
  svg += `<rect x="${ox}" y="${oy}" width="${dW}" height="${dH}" fill="none" stroke="#334060" stroke-width="1.5"/>`;

  // Dimension annotations
  const annotColor = '#3d5068';
  const af = 'font-family="JetBrains Mono,monospace"';
  svg += `<text x="${(ox+dW/2).toFixed(1)}" y="${(oy-7).toFixed(1)}" text-anchor="middle" ${af} font-size="9" fill="${annotColor}">${PL}"</text>`;
  svg += `<text x="${(ox-8).toFixed(1)}" y="${(oy+dH/2).toFixed(1)}" text-anchor="middle" ${af} font-size="9" fill="${annotColor}" `
       + `transform="rotate(-90,${(ox-8).toFixed(1)},${(oy+dH/2).toFixed(1)})">${PW}"</text>`;

  // Legend
  const ly = (oy + dH + 12).toFixed(1);
  svg += `<rect x="${ox}" y="${ly}" width="8" height="8" fill="rgba(245,166,35,.13)" stroke="#f5a623" stroke-width="0.7"/>`;
  svg += `<text x="${(ox+12).toFixed(1)}" y="${(parseFloat(ly)+7).toFixed(1)}" ${af} font-size="8" fill="#7a8faa">Standard</text>`;
  svg += `<rect x="${(ox+76).toFixed(1)}" y="${ly}" width="8" height="8" fill="rgba(52,212,200,.13)" stroke="#34d4c8" stroke-width="0.7"/>`;
  svg += `<text x="${(ox+88).toFixed(1)}" y="${(parseFloat(ly)+7).toFixed(1)}" ${af} font-size="8" fill="#7a8faa">Rotated 90°</text>`;

  svg += '</svg>';
  box.innerHTML = svg;
}

// ── Bulk Import ──────────────────────────────────────────────
function setupBulk() {
  const drop  = document.getElementById('drop-zone');
  const input = document.getElementById('file-input');

  drop.addEventListener('click',     () => input.click());
  drop.addEventListener('dragover',  e  => { e.preventDefault(); drop.classList.add('over'); });
  drop.addEventListener('dragleave', ()  => drop.classList.remove('over'));
  drop.addEventListener('drop',      e  => {
    e.preventDefault(); drop.classList.remove('over');
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
  input.addEventListener('change', () => { if (input.files[0]) handleFile(input.files[0]); });

  document.getElementById('bulk-calc-btn').addEventListener('click', doBulkCalc);
  document.getElementById('export-btn').addEventListener('click', exportResults);

  document.getElementById('dl-template').addEventListener('click', e => {
    e.preventDefault();
    const csv = 'sku,length,width,height\nITEM-001,12,8,6\nITEM-002,10,10,8\nITEM-003,14,6,5\n';
    dlString(csv, 'pallet-town-template.csv', 'text/csv');
  });
}

function handleFile(file) {
  const reader = new FileReader();
  reader.onload = e => {
    bulkData = parseCSV(e.target.result, file.name);
    if (bulkData.length) {
      setBulkStatus(`${bulkData.length} carton${bulkData.length !== 1 ? 's' : ''} loaded from ${file.name}`);
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
  const si = idx('sku'), li = idx('len'), wi = idx('wid'), hi = idx('hei');

  if (li === -1 || wi === -1 || hi === -1) {
    setBulkStatus('CSV needs length, width, height columns.', true);
    return [];
  }

  const rows = lines.slice(1).map((line, i) => {
    const cols = line.split(',').map(s => s.trim());
    const l = parseFloat(cols[li]), w = parseFloat(cols[wi]), h = parseFloat(cols[hi]);
    if (!l || !w || !h || l <= 0 || w <= 0 || h <= 0) return null;
    return {
      sku: si >= 0 ? cols[si] : `ROW-${i + 1}`,
      length: l, width: w, height: h,
    };
  }).filter(Boolean);

  if (!rows.length) { setBulkStatus('No valid rows found.', true); return []; }
  return rows;
}

async function doBulkCalc() {
  const rid = document.getElementById('bulk-retailer').value;
  const ds  = document.getElementById('bulk-ds').checked;
  const nop = document.getElementById('bulk-no-pallet').checked;

  if (!rid)              { setBulkStatus('Select a retailer.', true); return; }
  if (!bulkData.length)  { setBulkStatus('Upload a CSV first.', true); return; }

  setBtnState('bulk-calc-btn', 'bulk-btn-text', 'CALCULATING…', true);
  setBulkStatus(`Processing ${bulkData.length} cartons…`);

  try {
    const res  = await fetch(API.bulkCalc, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cartons: bulkData, retailer_id: rid, double_stack: ds,
                             exclude_pallet_height: nop }),
    });
    bulkResults = await res.json();
    if (!res.ok) { setBulkStatus(bulkResults.error || 'Error', true); return; }
    renderBulkTable(bulkResults);
    setBulkStatus(`${bulkResults.length} cartons calculated.`);
  } catch {
    setBulkStatus('Connection error.', true);
  } finally {
    setBtnState('bulk-calc-btn', 'bulk-btn-text', 'CALCULATE ALL', false);
  }
}

function renderBulkTable(rows) {
  const panel = document.getElementById('bulk-results');
  panel.style.display = 'flex';

  document.getElementById('table-body').innerHTML = rows.map(r => {
    const e = Math.round(r.efficiency * 100);
    const cls = e >= 80 ? 'hi' : e >= 60 ? 'mid' : 'lo';
    return `<tr>
      <td>${esc(r.sku)}</td>
      <td>${r.length}" × ${r.width}" × ${r.height}"</td>
      <td class="td-ti">${r.ti}</td>
      <td class="td-hi">${r.hi}</td>
      <td class="td-total">${r.total}</td>
      <td>${r.pod_length}" × ${r.pod_width}"</td>
      <td>${esc(r.arrangement_desc || '—')}</td>
      <td><span class="eff-badge ${cls}">${e}%</span></td>
    </tr>`;
  }).join('');
}

function exportResults() {
  if (!bulkResults.length) return;
  const head = 'SKU,Length,Width,Height,Ti,Hi,Total,Pod Length,Pod Width,Pattern,Efficiency\n';
  const body = bulkResults.map(r =>
    `${r.sku},${r.length},${r.width},${r.height},${r.ti},${r.hi},${r.total},${r.pod_length},${r.pod_width},"${(r.arrangement_desc || '').replace(/"/g, '""')}",${Math.round(r.efficiency * 100)}%`
  ).join('\n');
  dlString(head + body, 'pallet-results.csv', 'text/csv');
}

// ── Retailers tab ────────────────────────────────────────────
function setupRetailersTab() {
  document.getElementById('add-retailer-btn').addEventListener('click', addRetailer);
}

function renderRetailersGrid() {
  const grid = document.getElementById('retailers-grid');
  grid.innerHTML = retailers.map(r => cardHTML(r)).join('');
  grid.querySelectorAll('[data-action="edit"]').forEach(b   => b.addEventListener('click', () => startEdit(b.dataset.id)));
  grid.querySelectorAll('[data-action="delete"]').forEach(b => b.addEventListener('click', () => deleteRetailer(b.dataset.id)));
}

function cardHTML(r, editing = false) {
  if (editing) {
    return `<div class="r-card editing" id="rcard-${r.id}">
      <div class="r-card-head">
        <input class="r-name-input" id="e-name-${r.id}" value="${esc(r.name)}">
        <div class="r-card-btns">
          <button class="r-btn" data-action="save" data-id="${r.id}">SAVE</button>
          <button class="r-btn" data-action="cancel" data-id="${r.id}">CANCEL</button>
        </div>
      </div>
      <div class="r-fields">
        <div class="r-field r-field-full">
          <span class="r-field-label">MAX HEIGHT (in)</span>
          <input class="r-input" type="number" id="e-mh-${r.id}" value="${r.max_height}" step="0.5">
        </div>
        <div class="r-field r-field-full" style="margin-top:4px">
          <label class="toggle-label">
            <input type="checkbox" id="e-ds-${r.id}" class="toggle-input" ${r.double_stack_allowed ? 'checked' : ''}>
            <span class="toggle-track"><span class="toggle-thumb"></span></span>
            <span class="toggle-text">Double Stack Allowed</span>
          </label>
        </div>
      </div>
    </div>`;
  }

  const dsText = r.double_stack_allowed ? 'Allowed' : 'No';
  const dsCls  = r.double_stack_allowed ? 'yes' : 'no';

  return `<div class="r-card" id="rcard-${r.id}">
    <div class="r-card-head">
      <span class="r-card-name">${esc(r.name)}</span>
      <div class="r-card-btns">
        <button class="r-btn" data-action="edit" data-id="${r.id}">EDIT</button>
        <button class="r-btn danger" data-action="delete" data-id="${r.id}">DEL</button>
      </div>
    </div>
    <div class="r-fields">
      <div class="r-field">
        <span class="r-field-label">MAX HEIGHT</span>
        <span class="r-field-val">${r.max_height}"</span>
      </div>
      <div class="r-field">
        <span class="r-field-label">DOUBLE STACK</span>
        <span class="r-field-val ${dsCls}">${dsText}</span>
      </div>
    </div>
  </div>`;
}

function startEdit(id) {
  const r = retailerById(id);
  if (!r) return;
  const el = document.getElementById(`rcard-${id}`);
  el.outerHTML = cardHTML(r, true);
  document.querySelector(`[data-action="save"][data-id="${id}"]`).addEventListener('click',   () => saveRetailer(id));
  document.querySelector(`[data-action="cancel"][data-id="${id}"]`).addEventListener('click', () => renderRetailersGrid());
}

async function saveRetailer(id) {
  const payload = {
    name:                 document.getElementById(`e-name-${id}`).value,
    max_height:           parseFloat(document.getElementById(`e-mh-${id}`).value),
    double_stack_allowed: document.getElementById(`e-ds-${id}`).checked,
  };
  try {
    const res = await fetch(API.retailer(id), {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (res.ok) await loadRetailers();
  } catch (e) { console.error(e); }
}

async function deleteRetailer(id) {
  if (!confirm('Delete this retailer?')) return;
  try {
    await fetch(API.retailer(id), { method: 'DELETE' });
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
      body: JSON.stringify({ name: name.trim(), max_height: 60, pallet_length: 48, pallet_width: 40, pallet_height: 6.5, double_stack_allowed: false }),
    });
    if (res.ok) await loadRetailers();
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
