let META = null, PLAN = {}, SAVED = {}, ACTIVE = null, FILTER = '', PLAN_WRITTEN = false;
let CONTROL = { connected: false, state: 'offline' }, CONTROL_PENDING = null, CONTROL_NOTICE = '';
let CONTROL_OFFLINE_SINCE = null;
let SELECTED_PRESET = 'custom';
const CONTROL_TERMINAL_OUTCOMES = new Set(['started', 'rejected', 'stopped', 'paused', 'resumed', 'no-op']);
const CONTROL_QUEUE_TIMEOUT_MS = 45_000;
const CONTROL_OPERATION_TIMEOUT_MS = 5 * 60_000;
const CONTROL_OFFLINE_GRACE_MS = 5_000;
const REFRESHING = new Set();
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
const presetItems = () => META?.presets?.items || [];
const presetById = id => presetItems().find(preset => preset.id === id);

function initializePresets() {
  const select = $('presetSelect');
  for (const preset of presetItems()) {
    const item = document.createElement('option');
    item.value = preset.id;
    const script = String(preset.values?.['run.attack_script'] || 'Standard').replace(/^\[[^\]]+\][\s_-]*/, '');
    item.textContent = `TH ${preset.town_hall} — ${script === 'profile-current' ? 'Standard' : script}`;
    select.append(item);
  }
  select.onchange = () => {
    SELECTED_PRESET = select.value;
    $('applyPreset').disabled = SELECTED_PRESET === 'custom';
    renderPresetPreview();
  };
  $('applyPreset').onclick = applySelectedPreset;
  renderPresetPreview();
}

function markPresetCustom() {
  if (SELECTED_PRESET === 'custom') return;
  SELECTED_PRESET = 'custom';
  $('presetSelect').value = 'custom';
  $('applyPreset').disabled = true;
  renderPresetPreview();
}

function formatPresetValue(setting, value) {
  if (setting.type === 'boolean') return value ? 'On' : 'Off';
  if (setting.type === 'multi-select') {
    const labels = asList(value).map(id => optionOf(setting, id)?.label || id);
    return labels.length ? labels.join(', ') : 'None';
  }
  if (setting.type === 'select') return optionOf(setting, value)?.label || String(value);
  if (value === '' || value == null) return 'Blank';
  return `${value}${setting.unit ? ` ${setting.unit}` : ''}`;
}

function presetChanges(preset) {
  const values = preset.values || {};
  const preserved = new Set(META?.presets?.preserved_settings || []);
  return (META.sections || []).flatMap(section => settingsOf(section)
    .filter(setting => Object.prototype.hasOwnProperty.call(values, setting.id)
      && !preserved.has(setting.id)
      && !same(PLAN[setting.id], values[setting.id]))
    .map(setting => ({ section, setting, before: PLAN[setting.id], after: values[setting.id] })));
}

function buildPresetDiff(changes) {
  const details = document.createElement('details'); details.className = 'preset-diff';
  const toggle = document.createElement('summary');
  toggle.textContent = changes.length
    ? `Review ${changes.length} proposed change${changes.length === 1 ? '' : 's'}`
    : 'No field changes — the visible plan already matches';
  details.append(toggle);
  if (!changes.length) return details;

  const groups = new Map();
  for (const change of changes) {
    if (!groups.has(change.section.id)) groups.set(change.section.id, { section: change.section, changes: [] });
    groups.get(change.section.id).changes.push(change);
  }
  for (const group of groups.values()) {
    const section = document.createElement('section'); section.className = 'preset-diff-group';
    const heading = document.createElement('strong');
    heading.textContent = group.section.tab_label || group.section.title;
    const rows = document.createElement('dl');
    for (const change of group.changes) {
      const row = document.createElement('div');
      const label = document.createElement('dt'); label.textContent = change.setting.label;
      const values = document.createElement('dd');
      const before = document.createElement('del'); before.textContent = formatPresetValue(change.setting, change.before);
      const spoken = document.createElement('span'); spoken.className = 'sr-only'; spoken.textContent = ' becomes ';
      const arrow = document.createElement('span'); arrow.className = 'preset-diff-arrow'; arrow.textContent = '→'; arrow.setAttribute('aria-hidden', 'true');
      const after = document.createElement('ins'); after.textContent = formatPresetValue(change.setting, change.after);
      values.append(before, spoken, arrow, after); row.append(label, values); rows.append(row);
    }
    section.append(heading, rows); details.append(section);
  }
  return details;
}

function renderPresetPreview() {
  const preview = $('presetPreview');
  preview.replaceChildren();
  delete preview.dataset.compatibility;
  const preset = presetById(SELECTED_PRESET);
  if (!preset) {
    const title = document.createElement('strong'); title.textContent = 'Custom plan';
    const note = document.createElement('span');
    note.textContent = 'Select a Town Hall to preview its changes. Nothing is changed or saved yet.';
    preview.append(title, note);
    return;
  }

  preview.dataset.compatibility = preset.compatibility;
  const changes = presetChanges(preset);
  const changed = changes.length;
  const title = document.createElement('strong'); title.textContent = `${preset.label} / ${changed} field${changed === 1 ? '' : 's'} would change`;
  const summary = document.createElement('span'); summary.textContent = preset.description;
  const facts = document.createElement('span'); facts.className = 'preset-facts';
  const scriptSetting = findSetting('run.attack_script');
  const script = optionOf(scriptSetting || {}, preset.values?.['run.attack_script']);
  const heroSetting = findSetting('run.heroes');
  const choosesHeroes = Object.prototype.hasOwnProperty.call(preset.values || {}, 'run.heroes');
  const heroes = asList(preset.values?.['run.heroes']).map(id => optionOf(heroSetting || {}, id)?.label || id);
  const factValues = [
    `Script: ${script?.label || 'Profile selection'}`,
    `Heroes: ${choosesHeroes ? (heroes.length ? heroes.join(', ') : 'none') : 'keep visible selection'}`,
    `Limit: ${preset.values?.['run.max_battles'] || 0} battles / ${preset.values?.['run.duration_minutes'] || 0} min`,
  ];
  for (const value of factValues) {
    const fact = document.createElement('span'); fact.textContent = value; facts.append(fact);
  }
  const army = document.createElement('span'); army.className = 'preset-army-note';
  army.textContent = preset.compatibility === 'script-declared'
    ? 'Deployment only: no CSV training table is imported. Confirm the active profile army matches the selected script.'
    : 'Standard fallback: the active profile army and visible Hero selection are retained.';
  const basis = document.createElement('span'); basis.className = 'preset-basis';
  basis.textContent = `${preset.compatibility === 'script-declared' ? 'Script-declared compatibility' : 'Engine-compatible fallback'} — ${preset.source_note}`;
  const safety = document.createElement('span');
  safety.textContent = 'Apply preset only loads the visible fields. Apply plan is still required to save; Start remains separate.';
  preview.append(title, summary, facts, army, basis, buildPresetDiff(changes), safety);
}

function applySelectedPreset() {
  const preset = presetById(SELECTED_PRESET);
  if (!preset) return;
  const preserved = new Set(META?.presets?.preserved_settings || []);
  for (const [id, value] of Object.entries(preset.values || {})) {
    if (!findSetting(id) || preserved.has(id)) continue;
    PLAN[id] = structuredClone(value);
  }
  drawNav(); drawPanel(); updateBanner(); updateDirty(); renderPresetPreview();
  $('status').className = 'status warn';
  $('status').textContent = `${preset.label} loaded for review — press Apply plan to write it.`;
}

async function boot() {
  const res = await fetch('/api/metadata').then(r => r.json());
  META = res.metadata;
  PLAN = await fetch('/api/plan').then(r => r.json());
  const health = await fetch('/api/health').then(r => r.json());
  PLAN_WRITTEN = health.plan?.state === 'saved';
  SAVED = structuredClone(PLAN);
  $('plannerTitle').textContent = META.title || 'Run Planner';
  $('lede').textContent = META.description || '';
  initializePresets();

  const fromHash = location.hash.replace('#', '');
  ACTIVE = (META.sections || []).some(s => s.id === fromHash) ? fromHash : (META.sections || [])[0]?.id;
  drawNav(); drawPanel(); updateBanner(); updateDirty(); pollEvents(); pollControl();

  window.addEventListener('hashchange', () => {
    const id = location.hash.replace('#', '');
    if ((META.sections || []).some(s => s.id === id) && id !== ACTIVE) { ACTIVE = id; drawNav(); drawPanel(); }
  });
  $('filter').oninput = e => { FILTER = e.target.value.trim().toLowerCase(); drawNav(); drawPanel(); };
}

// Filtering searches every section, not just the open one: with 43 settings across 13 pages, the
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
    b.classList.toggle('filter-empty', Boolean(FILTER && !hits));

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
  revert.onclick = () => { PLAN[setting.id] = structuredClone(defaultFor(setting)); markPresetCustom(); refresh(setting); };
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
  control.onchange = () => { PLAN[setting.id] = readControl(setting, control); markPresetCustom(); refresh(setting); };

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
      markPresetCustom();
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
  if (REFRESHING.has(setting.id)) return;
  REFRESHING.add(setting.id);
  try {
    const row = $('panel').querySelector(`[data-setting="${CSS.escape(setting.id)}"]`);
    if (row?.parentNode) row.parentNode.replaceChild(renderRow(setting), row);
    if (setting.id === 'run.surface') updateBanner();
    showDetail(setting);
    drawNav();
    updateDirty();
  } finally {
    REFRESHING.delete(setting.id);
  }
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
  $('apply').disabled = !pending && PLAN_WRITTEN;
  $('dirty').textContent = pending
    ? `${pending} unsaved change${pending === 1 ? '' : 's'}`
    : (!PLAN_WRITTEN ? 'Defaults not yet applied'
      : (changed ? `${changed} setting${changed === 1 ? '' : 's'} differ from default` : 'Matches defaults'));
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
  $('engineProfile').textContent = connected ? (CONTROL.profile || 'Default') : 'Not connected';
  $('engineEmulator').textContent = connected
    ? ([CONTROL.emulator, CONTROL.instance].filter(Boolean).join(' / ') || 'Not selected')
    : 'Not connected';
  $('engineVersion').textContent = connected && CONTROL.engine_version ? `Upstream ${CONTROL.engine_version}` : 'Not connected';

  setHealth('healthUi', 'ready', 'Ready');
  setHealth('healthNative', connected ? 'ready' : 'waiting', connected ? 'Connected' : 'Waiting');
  if (!connected) {
    setHealth('healthEngine', 'waiting', 'Waiting');
  } else if (CONTROL.engine_available === false) {
    setHealth('healthEngine', 'error', 'Unavailable');
  } else if (CONTROL.engine_probe_state === 'running') {
    setHealth('healthEngine', 'warning', 'Checking');
  } else if (CONTROL.engine_probe_state === 'passed') {
    setHealth('healthEngine', 'ready', 'Ready');
  } else {
    setHealth('healthEngine', 'warning', 'Not checked');
  }
  const emulator = [CONTROL.emulator, CONTROL.instance].filter(Boolean).join(' / ');
  const windowAttached = connected && (CONTROL.window_attached === true || CONTROL.emulator_attached === true);
  const adbReady = connected && CONTROL.adb_ready === true;
  const gameReady = connected && CONTROL.game_ready === true;
  let emulatorState = connected ? 'warning' : 'waiting';
  let emulatorText = connected ? (emulator ? 'Not attached' : 'Not selected') : 'Waiting';
  if (windowAttached) emulatorText = 'Window found';
  if (adbReady) emulatorText = 'ADB ready';
  if (gameReady) {
    emulatorState = 'ready';
    emulatorText = emulator ? `${emulator} / game ready` : 'Game ready';
  }
  setHealth('healthEmulator', emulatorState, emulatorText);

  const busy = !!CONTROL_PENDING;
  const startCanBeStopped = CONTROL_PENDING?.action === 'start' && !!CONTROL_PENDING.request_id;
  const engineAvailable = CONTROL.engine_available !== false;
  if (connected && !engineAvailable) $('engineState').textContent = 'Engine unavailable';
  $('controlStart').textContent = 'Start run';
  $('controlStart').title = 'Start the native run';
  $('controlStart').disabled = busy || !connected || !engineAvailable || state !== 'idle';
  $('controlPause').disabled = busy || !connected || !['running', 'paused'].includes(state);
  $('controlStop').disabled = !connected || (busy && !startCanBeStopped)
    || (!startCanBeStopped && !['starting', 'running', 'paused'].includes(state));
  $('controlPause').textContent = state === 'paused' ? 'Resume' : 'Pause';

  if (CONTROL_PENDING) {
    const phase = CONTROL_PENDING.phase === 'saving'
      ? 'saving the visible plan before queueing'
      : (CONTROL_PENDING.accepted_at ? 'accepted; waiting for completion' : 'queued; waiting for native acknowledgement');
    const cancellation = startCanBeStopped ? ' Stop remains available.' : '';
    $('controlAck').textContent = `${CONTROL_PENDING.action} command ${phase}...${cancellation}`;
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

function recoverControlPending(now = Date.now()) {
  if (!CONTROL_PENDING) {
    CONTROL_OFFLINE_SINCE = null;
    return;
  }
  if (!CONTROL.connected) {
    if (CONTROL_OFFLINE_SINCE == null) CONTROL_OFFLINE_SINCE = now;
    if (now - CONTROL_OFFLINE_SINCE >= CONTROL_OFFLINE_GRACE_MS) {
      CONTROL_NOTICE = `${CONTROL_PENDING.action} tracking cleared because the native engine went offline before a terminal outcome.`;
      CONTROL_PENDING = null;
      CONTROL_OFFLINE_SINCE = null;
    }
    return;
  }

  CONTROL_OFFLINE_SINCE = null;
  const accepted = !!CONTROL_PENDING.accepted_at;
  const startedAt = accepted ? CONTROL_PENDING.accepted_at : CONTROL_PENDING.queued_at;
  const timeout = accepted ? CONTROL_OPERATION_TIMEOUT_MS : CONTROL_QUEUE_TIMEOUT_MS;
  if (startedAt && now - startedAt >= timeout) {
    const wait = accepted ? 'completion' : 'native acknowledgement';
    CONTROL_NOTICE = `${CONTROL_PENDING.action} tracking cleared after no ${wait} arrived within ${Math.round(timeout / 1000)} seconds.`;
    CONTROL_PENDING = null;
  }
}

function setHealth(id, state, label) {
  const step = $(id);
  step.dataset.state = state;
  step.querySelector('strong').textContent = label;
}

async function pollControl() {
  try {
    CONTROL = await fetch('/api/control/status').then(r => r.json());
    if (CONTROL_PENDING && CONTROL_PENDING.request_id
        && CONTROL.last_command_id === CONTROL_PENDING.request_id
        && CONTROL.last_command === CONTROL_PENDING.action) {
      const outcome = CONTROL.last_outcome || '';
      if (outcome === 'accepted') {
        if (!CONTROL_PENDING.accepted_at) CONTROL_PENDING.accepted_at = Date.now();
      } else if (CONTROL_TERMINAL_OUTCOMES.has(outcome)) {
        CONTROL_NOTICE = `${outcome}: ${CONTROL.last_command_message || CONTROL.message || `${CONTROL_PENDING.action} command processed`}`;
        CONTROL_PENDING = null;
      }
    }
  } catch {
    CONTROL = { connected: false, state: 'offline', message: 'Control service is unreachable.' };
  }
  recoverControlPending();
  renderControl();
  setTimeout(pollControl, 1000);
}

async function sendControl(action) {
  const previousPending = CONTROL_PENDING;
  const replacingStart = action === 'stop' && previousPending?.action === 'start' && !!previousPending.request_id;
  if (CONTROL_PENDING && !replacingStart) return;
  if (action === 'start') {
    const savingStart = {
      action,
      request_id: null,
      queued_at: Date.now(),
      accepted_at: null,
      phase: 'saving'
    };
    CONTROL_PENDING = savingStart;
    CONTROL_NOTICE = 'Saving the visible plan before Start...';
    renderControl();
    const saved = await savePlan();
    // Poll recovery can invalidate a slow request. Never let that older save
    // queue a Start after the UI has already recovered or begun another action.
    if (CONTROL_PENDING !== savingStart) return;
    if (!saved) {
      CONTROL_PENDING = null;
      CONTROL_NOTICE = 'Start stopped because the visible plan could not be saved.';
      renderControl();
      return;
    }
    savingStart.phase = 'queueing';
    savingStart.queued_at = Date.now();
  }
  CONTROL_NOTICE = '';
  if (action !== 'start') {
    CONTROL_PENDING = { action, request_id: null, queued_at: Date.now(), accepted_at: null, phase: 'queueing' };
  }
  renderControl();
  try {
    const response = await fetch('/api/control/command', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action })
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      CONTROL_NOTICE = (payload.problems || ['Command was refused.']).join('; ');
      CONTROL_PENDING = replacingStart ? previousPending : null;
    } else {
      CONTROL_PENDING = { action, request_id: payload.request_id, queued_at: Date.now(), accepted_at: null, phase: 'queued' };
    }
  } catch {
    CONTROL_NOTICE = 'Could not reach the local control service.';
    CONTROL_PENDING = replacingStart ? previousPending : null;
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

async function savePlan() {
  const s = $('status');
  try {
    const response = await fetch('/api/plan', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(PLAN)
    });
    const r = await response.json();
    if (!response.ok || !r.ok) {
      s.className = 'status bad';
      s.textContent = (r.problems || ['failed']).join('; ');
      return false;
    }
    // The server clamps and coerces, so what it accepted is now the truth, not what was on screen.
    PLAN = r.plan;
    SAVED = structuredClone(PLAN);
    PLAN_WRITTEN = true;
    drawNav(); drawPanel(); updateBanner(); updateDirty();
    s.className = r.problems.length ? 'status warn' : 'status ok';
    s.textContent = r.problems.length ? r.problems.join('; ') : 'Saved to ' + r.written;
    return true;
  } catch (err) {
    s.className = 'status bad';
    s.textContent = 'Could not reach the planner server.';
    return false;
  }
}

$('apply').onclick = () => savePlan();

$('reset').onclick = () => {
  for (const s of allSettings()) PLAN[s.id] = structuredClone(defaultFor(s));
  markPresetCustom();
  drawNav(); drawPanel(); updateBanner(); updateDirty();
  $('status').className = 'status';
  $('status').textContent = 'Reset to defaults — press Apply to write it.';
};

$('controlStart').onclick = () => sendControl('start');
$('controlPause').onclick = () => sendControl(CONTROL.state === 'paused' ? 'resume' : 'pause');
$('controlStop').onclick = () => sendControl('stop');

$('exportDiagnostics').onclick = async () => {
  const button = $('exportDiagnostics');
  button.disabled = true;
  const original = button.textContent;
  button.textContent = 'Preparing...';
  try {
    const response = await fetch('/api/diagnostics');
    if (!response.ok) throw new Error('download refused');
    const blob = await response.blob();
    const match = /filename="([^"]+)"/.exec(response.headers.get('Content-Disposition') || '');
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = match ? match[1] : 'my-bot-diagnostics.json';
    document.body.append(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(link.href);
    CONTROL_NOTICE = 'Diagnostic bundle exported. It contains operational state only.';
  } catch {
    CONTROL_NOTICE = 'Diagnostic export failed. The local service may be unavailable.';
  } finally {
    button.disabled = false;
    button.textContent = original;
    renderControl();
  }
};

function escapeHtml(s) {
  return String(s ?? '').replace(/[&<>"']/g, c =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

boot();
