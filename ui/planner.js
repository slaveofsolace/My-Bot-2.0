let META = null, PLAN = {}, SAVED = {}, ACTIVE = null, FILTER = '';
let CONTROL = { connected: false, state: 'offline' }, CONTROL_PENDING = null, CONTROL_NOTICE = '';
const $ = id => document.getElementById(id);

const settingsOf = s => s.settings || [];
const allSettings = () => (META.sections || []).flatMap(settingsOf);
const findSetting = id => allSettings().find(s => s.id === id);
const optionOf = (s, v) => (s.options || []).find(o => o.value === v);

// Multi-select values travel as arrays; everything else is a scalar. Normalising here means the
// comparison, the chips, and the POST body all agree on the shape.
const asList = v => Array.isArray(v) ? v : (v === '' || v == null ? [] : [v]);
const defaultFor = s => s.type === 'multi-select' ? asList(s.default) : s.default;
const same = (a, b) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null);
const isChanged = s => !same(PLAN[s.id], defaultFor(s));
const isUnsaved = s => !same(PLAN[s.id], SAVED[s.id]);

async function boot() {
  const res = await fetch('/api/metadata').then(r => r.json());
  META = res.metadata;
  PLAN = await fetch('/api/plan').then(r => r.json());
  SAVED = structuredClone(PLAN);
  $('plannerTitle').textContent = META.title || 'Run Planner';
  $('lede').textContent = META.description || '';

  const fromHash = location.hash.replace('#', '');
  ACTIVE = (META.sections || []).some(s => s.id === fromHash) ? fromHash : (META.sections || [])[0]?.id;
  drawNav(); drawPanel(); updateBanner(); updateDirty(); pollEvents(); pollControl();

  window.addEventListener('hashchange', () => {
    const id = location.hash.replace('#', '');
    if ((META.sections || []).some(s => s.id === id) && id !== ACTIVE) { ACTIVE = id; drawNav(); drawPanel(); }
  });
  $('filter').oninput = e => { FILTER = e.target.value.trim().toLowerCase(); drawNav(); drawPanel(); };
}

// Filtering searches every section, not just the open one: with 42 settings across 13 pages, the
// thing you are looking for is usually not on the page you are standing on.
function matches(setting) {
  if (!FILTER) return true;
  return [setting.label, setting.summary, setting.description, setting.id]
    .some(t => String(t ?? '').toLowerCase().includes(FILTER));
}
const visibleIn = section => settingsOf(section).filter(matches);

function drawNav() {
  const nav = $('nav');
  nav.innerHTML = '';
  for (const section of META.sections || []) {
    const hits = visibleIn(section).length;
    const b = document.createElement('button');
    b.setAttribute('aria-current', String(section.id === ACTIVE));
    if (FILTER && !hits) b.style.opacity = '.35';

    const name = document.createElement('span');
    name.textContent = section.tab_label || section.title;
    b.append(name);

    // Tally shows filter hits while searching, and otherwise how many settings differ from default.
    const tally = document.createElement('span');
    tally.className = 'tally';
    const changed = settingsOf(section).filter(isChanged).length;
    const n = FILTER ? hits : changed;
    tally.textContent = n;
    tally.hidden = !n;
    b.append(tally);

    b.onclick = () => { ACTIVE = section.id; location.hash = section.id; drawNav(); drawPanel(); };
    nav.append(b);
  }
}

function drawPanel() {
  const section = (META.sections || []).find(s => s.id === ACTIVE);
  const el = $('panel');
  el.innerHTML = '';
  if (!section) return;

  const h = document.createElement('h2'); h.textContent = section.title;
  const p = document.createElement('p'); p.className = 'lede'; p.textContent = section.description;
  el.append(h, p);

  const rows = visibleIn(section);
  if (!rows.length) {
    const empty = document.createElement('p');
    empty.className = 'empty';
    empty.textContent = FILTER ? `Nothing in ${section.title} matches “${FILTER}”.` : 'No settings here.';
    el.append(empty);
    return;
  }
  for (const setting of rows) el.append(renderRow(setting));
}

function renderRow(setting) {
  const row = document.createElement('div');
  row.className = 'row' + (isChanged(setting) ? ' changed' : '');
  row.dataset.setting = setting.id;

  const label = document.createElement('label');
  label.htmlFor = 'f_' + setting.id;
  label.innerHTML = escapeHtml(setting.label) + (setting.required ? '<span class="req">*</span>' : '');

  // Reverting one setting is far more common than resetting the lot, and it is only offered on the
  // rows where it would do something.
  const revert = document.createElement('button');
  revert.className = 'revert'; revert.type = 'button';
  revert.textContent = 'revert'; revert.title = 'Put this setting back to its default';
  revert.onclick = () => { PLAN[setting.id] = structuredClone(defaultFor(setting)); refresh(setting); };
  label.append(revert);

  const note = document.createElement('span');
  note.className = 'note'; note.textContent = setting.summary;
  label.append(note);

  const field = document.createElement('div'); field.className = 'field';
  buildField(setting, field);

  row.append(label, field);
  return row;
}

function buildField(setting, field) {
  if (setting.type === 'multi-select') { buildChips(setting, field); return; }

  const control = makeControl(setting);
  control.id = 'f_' + setting.id;
  control.onfocus = () => showDetail(setting);
  control.onchange = () => { PLAN[setting.id] = readControl(setting, control); refresh(setting); };

  if (setting.type === 'boolean') {
    const wrap = document.createElement('span');
    wrap.className = 'switch';
    const track = document.createElement('span'); track.className = 'track';
    const knob = document.createElement('span'); knob.className = 'knob';
    wrap.append(control, track, knob);
    field.append(wrap);
    const hint = document.createElement('span');
    hint.className = 'unit'; hint.textContent = setting.summary;
    field.append(hint);
  } else {
    field.append(control);
    if (setting.unit) {
      const u = document.createElement('span'); u.className = 'unit'; u.textContent = setting.unit;
      field.append(u);
    }
  }
  if ((setting.options || []).length) paintAvailability(setting, field);
}

// The Hero Hall holds six but only four can be active, so this is a selection with a ceiling rather
// than a dropdown. A single select could never express it, which is what it used to be.
function buildChips(setting, field) {
  const chosen = asList(PLAN[setting.id]);
  const max = setting.max_selected || setting.options.length;

  const chips = document.createElement('div'); chips.className = 'chips';
  for (const option of setting.options) {
    const on = chosen.includes(option.value);
    const chip = document.createElement('button');
    chip.type = 'button'; chip.className = 'chip'; chip.textContent = option.label;
    chip.setAttribute('aria-pressed', String(on));
    chip.disabled = !on && chosen.length >= max;
    chip.title = option.summary || '';
    chip.onfocus = () => showDetail(setting, option);
    chip.onclick = () => {
      const next = asList(PLAN[setting.id]);
      const at = next.indexOf(option.value);
      if (at >= 0) next.splice(at, 1);
      else if (next.length < max) next.push(option.value);
      PLAN[setting.id] = next;
      refresh(setting);
    };
    chips.append(chip);
  }
  field.append(chips);

  const slots = document.createElement('span');
  slots.className = 'slots';
  slots.textContent = `${chosen.length} of ${max} slots used`;
  field.append(slots);
}

// Redraw just enough: the row itself, the nav tallies, and anything derived from this setting.
function refresh(setting) {
  const row = $('panel').querySelector(`[data-setting="${CSS.escape(setting.id)}"]`);
  if (row) row.replaceWith(renderRow(setting));
  if (setting.id === 'run.surface') updateBanner();
  showDetail(setting);
  drawNav();
  updateDirty();
}

// Availability shown as a pill plus the specific blocking reason, so "greyed out" is never mysterious.
function paintAvailability(setting, field) {
  const opt = optionOf(setting, PLAN[setting.id]);
  if (!opt) return;

  const pill = document.createElement('span');
  pill.className = 'pill ' + opt.availability;
  pill.textContent = { available: 'verified', gated: 'unverified',
                       planned: 'not implemented', unsupported: 'unsupported' }[opt.availability] || opt.availability;
  const line = document.createElement('div');
  line.className = 'availability';
  line.append(pill);
  field.append(line);

  if (opt.disabled_reason) {
    const why = document.createElement('div'); why.className = 'why';
    why.textContent = opt.disabled_reason;
    field.append(why);
  }
}

function makeControl(setting) {
  if (setting.type === 'boolean') {
    const c = document.createElement('input'); c.type = 'checkbox';
    c.checked = !!PLAN[setting.id]; return c;
  }
  if (setting.type === 'integer') {
    const c = document.createElement('input'); c.type = 'number';
    const v = setting.validation || {};
    if (v.minimum !== undefined) c.min = v.minimum;
    if (v.maximum !== undefined) c.max = v.maximum;
    if (v.step !== undefined) c.step = v.step;
    c.value = PLAN[setting.id] ?? defaultFor(setting) ?? 0; return c;
  }
  if ((setting.options || []).length) {
    const c = document.createElement('select');
    for (const o of setting.options) {
      const opt = document.createElement('option');
      opt.value = o.value;
      opt.textContent = o.label + (o.recommended ? '  (recommended)' : '');
      c.append(opt);
    }
    c.value = PLAN[setting.id] ?? defaultFor(setting); return c;
  }
  const c = document.createElement('input'); c.type = 'text';
  c.value = PLAN[setting.id] ?? '';
  c.placeholder = setting.empty_state || ''; return c;
}

function readControl(setting, c) {
  if (setting.type === 'boolean') return c.checked;
  if (setting.type === 'integer') return c.value === '' ? 0 : Number(c.value);
  return c.value;
}

function showDetail(setting, forced) {
  const parts = ['<strong>' + escapeHtml(setting.label) + '</strong><br>' + escapeHtml(setting.description)];
  const opt = forced || optionOf(setting, PLAN[setting.id]);
  if (opt) {
    parts.push('<br><br><strong>' + escapeHtml(opt.label) + '</strong><br>' + escapeHtml(opt.description));
    if ((opt.prerequisites || []).length) {
      parts.push('<br><br><strong>Needs</strong><ul>' +
        opt.prerequisites.map(p => '<li>' + escapeHtml(p) + '</li>').join('') + '</ul>');
    }
    if (opt.disabled_reason) parts.push('<br><strong>Not verified:</strong> ' + escapeHtml(opt.disabled_reason));
    if (opt.warning) parts.push('<br><br><strong>Note:</strong> ' + escapeHtml(opt.warning));
  }
  $('detail').innerHTML = parts.join('');
}

function updateBanner() {
  const setting = findSetting('run.surface');
  const opt = setting && optionOf(setting, PLAN['run.surface']);
  const b = $('banner');
  const verified = opt && opt.availability === 'available';
  b.className = 'banner' + (verified ? ' verified' : '');
  b.querySelector('.mark').textContent = verified ? '✓' : '!';
  $('bannerText').textContent = verified
    ? 'Verified: this surface has been demonstrated on the current client.'
    : 'Diagnostic run: this surface has not been demonstrated on the current client. '
      + (opt ? opt.disabled_reason + ' ' : '')
      + 'Treat every result as an observation, not a confirmed capability.';
}

// Knowing whether the screen matches the file is the difference between "I changed that" and
// "I changed that and it is live". Apply is disabled when there is nothing to write.
function updateDirty() {
  const pending = allSettings().filter(isUnsaved).length;
  const changed = allSettings().filter(isChanged).length;
  $('apply').disabled = !pending;
  $('dirty').textContent = pending
    ? `${pending} unsaved change${pending === 1 ? '' : 's'}`
    : (changed ? `${changed} setting${changed === 1 ? '' : 's'} differ from default` : 'Matches defaults');
}

function readableState(state) {
  return ({ offline: 'Engine offline', idle: 'Ready', starting: 'Starting', running: 'Run active',
            paused: 'Run paused', stopping: 'Stopping', closing: 'Closing', error: 'Status error' })[state]
    || String(state || 'Unknown');
}

function renderControl() {
  const connected = !!CONTROL.connected;
  const state = connected ? (CONTROL.state || 'idle') : 'offline';
  $('engineLamp').dataset.state = state;
  $('engineState').textContent = readableState(state);
  $('engineMessage').textContent = CONTROL.message || (connected ? 'Native engine connected.' : 'Launch My Bot 2.0 to enable run controls.');
  $('engineProfile').textContent = CONTROL.profile || 'Default';
  $('engineEmulator').textContent = [CONTROL.emulator, CONTROL.instance].filter(Boolean).join(' / ') || 'Not selected';
  $('engineVersion').textContent = CONTROL.engine_version ? `MyBot.run ${CONTROL.engine_version}` : 'Not connected';

  const busy = !!CONTROL_PENDING;
  $('controlStart').disabled = busy || !connected || state !== 'idle';
  $('controlPause').disabled = busy || !connected || !['running', 'paused'].includes(state);
  $('controlStop').disabled = busy || !connected || !['starting', 'running', 'paused'].includes(state);
  $('controlPause').textContent = state === 'paused' ? 'Resume' : 'Pause';

  if (CONTROL_PENDING) {
    $('controlAck').textContent = `${CONTROL_PENDING.action} command queued; waiting for native acknowledgement...`;
    $('controlAck').className = 'control-ack pending';
  } else if (CONTROL_NOTICE) {
    $('controlAck').textContent = CONTROL_NOTICE;
    $('controlAck').className = 'control-ack notice';
  } else {
    $('controlAck').textContent = connected
      ? `Heartbeat ${Math.round(Number(CONTROL.age_seconds || 0))}s ago${CONTROL.bot_pid ? ` / PID ${CONTROL.bot_pid}` : ''}.`
      : 'Commands stay disabled until a fresh native heartbeat is present.';
    $('controlAck').className = 'control-ack';
  }
}

async function pollControl() {
  try {
    CONTROL = await fetch('/api/control/status').then(r => r.json());
    if (CONTROL_PENDING && CONTROL_PENDING.request_id
        && CONTROL.last_command_id === CONTROL_PENDING.request_id) {
      const outcome = CONTROL.last_outcome || 'acknowledged';
      CONTROL_NOTICE = `${outcome}: ${CONTROL.last_command_message || CONTROL.message || `${CONTROL_PENDING.action} command processed`}`;
      CONTROL_PENDING = null;
    }
  } catch {
    CONTROL = { connected: false, state: 'offline', message: 'Control service is unreachable.' };
  }
  renderControl();
  setTimeout(pollControl, 1000);
}

async function sendControl(action) {
  if (CONTROL_PENDING) return;
  CONTROL_NOTICE = '';
  CONTROL_PENDING = { action, request_id: null };
  renderControl();
  try {
    const response = await fetch('/api/control/command', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action })
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      CONTROL_NOTICE = (payload.problems || ['Command was refused.']).join('; ');
      CONTROL_PENDING = null;
    } else {
      CONTROL_PENDING = { action, request_id: payload.request_id };
    }
  } catch {
    CONTROL_NOTICE = 'Could not reach the local control service.';
    CONTROL_PENDING = null;
  }
  renderControl();
}

async function pollEvents() {
  try {
    const { events } = await fetch('/api/events').then(r => r.json());
    const ul = $('events');
    ul.innerHTML = events.length ? '' : '<li>No events yet.</li>';
    for (const e of events.slice(-14).reverse()) {
      const li = document.createElement('li');
      li.className = e.severity || 'info';
      li.innerHTML = '<span class="dot"></span>' + escapeHtml(e.type || '') + ' — ' + escapeHtml(e.message || '');
      ul.append(li);
    }
  } catch {}
  setTimeout(pollEvents, 3000);
}

$('apply').onclick = async () => {
  const s = $('status');
  try {
    const r = await fetch('/api/plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(PLAN)
    }).then(r => r.json());
    if (!r.ok) { s.className = 'status bad'; s.textContent = (r.problems || ['failed']).join('; '); return; }
    // The server clamps and coerces, so what it accepted is now the truth, not what was on screen.
    PLAN = await fetch('/api/plan').then(r => r.json());
    SAVED = structuredClone(PLAN);
    drawNav(); drawPanel(); updateBanner(); updateDirty();
    s.className = r.problems.length ? 'status warn' : 'status ok';
    s.textContent = r.problems.length ? r.problems.join('; ') : 'Saved to ' + r.written;
  } catch (err) {
    s.className = 'status bad';
    s.textContent = 'Could not reach the planner server.';
  }
};

$('reset').onclick = () => {
  for (const s of allSettings()) PLAN[s.id] = structuredClone(defaultFor(s));
  drawNav(); drawPanel(); updateBanner(); updateDirty();
  $('status').className = 'status';
  $('status').textContent = 'Reset to defaults — press Apply to write it.';
};

$('controlStart').onclick = () => sendControl('start');
$('controlPause').onclick = () => sendControl(CONTROL.state === 'paused' ? 'resume' : 'pause');
$('controlStop').onclick = () => sendControl('stop');

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

boot();
