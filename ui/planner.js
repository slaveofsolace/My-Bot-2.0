let META = null;
let PLAN = {};
let SAVED = {};
let FILTER = '';
let PLAN_WRITTEN = false;
let NATIVE_PROFILE_MODE = false;
let BOOT_READY = false;
let ACTIVE_VIEW = 'run';
const VIEW_IDS = ['run', 'plan', 'village', 'activity', 'diagnostics'];
let ACTIVE_GROUP = 'match';
let SELECTED_PRESET = 'custom';
let LOADED_SAFETY_PATCH = null;
let CAPABILITY_CATALOG = { capabilities: [], status_definitions: {} };
let EVIDENCE_READINESS = null;

// Route selectors may load a complete, visible safety contract, but never save or start it. Keeping
// these patches keyed by strategy makes later single-purpose Home routes explicit rather than a
// growing set of special-case onchange branches.
const STRATEGY_SAFETY_PATCHES = {
  'home.collectors': {
    label: 'Home-maintenance safety settings',
    values: {
      'run.surface': 'regular', 'run.strategy': 'home.collectors', 'run.attack_script': 'profile-current',
      'run.town_hall': 0, 'run.heroes': [], 'run.duration_minutes': 0, 'run.max_battles': 0,
      'run.stop_on_star_bonus': false, 'run.max_failures': 0,
      'target.gold': 0, 'target.elixir': 0, 'target.dark_elixir': 0,
      'upgrade.policy': 'disabled', 'account.queue': '',
      'army.source': 'recipe', 'army.recipe_name': '', 'army.manage_training': false,
      'army.wait_for_full': false, 'army.train_spells': false, 'army.train_sieges': false,
      'search.min_gold': 0, 'search.min_elixir': 0, 'search.min_dark': 0,
      'search.max_seconds': 0, 'search.town_hall_filter': 'any',
      'donate.mode': 'off', 'donate.keep_army': true, 'donate.max_per_run': 0,
      'donate.request_when_short': false,
      'events.clan_games': false, 'events.clan_games_point_cap': 0,
      'events.laboratory': 'off', 'events.collect_resources': true, 'events.collect_daily_reward': false,
      'events.collect_loot_cart': false,
      'events.collect_treasury': false,
      'notify.on_stop': true, 'notify.on_error': true, 'notify.channel': 'log-only',
      'pacing.action_delay_ms': 180, 'pacing.settle_ms': 650, 'pacing.retry_attempts': 0,
      'pacing.break_every_minutes': 0, 'pacing.break_minutes': 5,
    },
  },
  'home.clan-request': {
    label: 'Clan-request-only safety settings',
    values: {
      'run.surface': 'regular', 'run.strategy': 'home.clan-request', 'run.attack_script': 'profile-current',
      'run.town_hall': 0, 'run.heroes': [], 'run.duration_minutes': 0, 'run.max_battles': 0,
      'run.stop_on_star_bonus': false, 'run.max_failures': 0,
      'target.gold': 0, 'target.elixir': 0, 'target.dark_elixir': 0,
      'upgrade.policy': 'disabled', 'account.queue': '',
      'army.source': 'recipe', 'army.recipe_name': '', 'army.manage_training': false,
      'army.wait_for_full': false, 'army.train_spells': false, 'army.train_sieges': false,
      'search.min_gold': 0, 'search.min_elixir': 0, 'search.min_dark': 0,
      'search.max_seconds': 0, 'search.town_hall_filter': 'any',
      'donate.mode': 'off', 'donate.keep_army': true, 'donate.max_per_run': 0,
      'donate.request_when_short': true,
      'events.clan_games': false, 'events.clan_games_point_cap': 0,
      'events.laboratory': 'off', 'events.collect_resources': false, 'events.collect_daily_reward': false,
      'events.collect_loot_cart': false,
      'events.collect_treasury': false,
      'notify.on_stop': true, 'notify.on_error': true, 'notify.channel': 'log-only',
      'pacing.action_delay_ms': 180, 'pacing.settle_ms': 650, 'pacing.retry_attempts': 0,
      'pacing.break_every_minutes': 0, 'pacing.break_minutes': 5,
    },
  },
};

const MAINTENANCE_COLLECTIONS = Object.freeze([
  { id: 'events.collect_resources', label: 'Collectors' },
  { id: 'events.collect_loot_cart', label: 'Loot Cart' },
  { id: 'events.collect_treasury', label: 'Treasury' },
  { id: 'events.collect_daily_reward', label: 'Daily Reward' },
]);

let CONTROL = { connected: false, state: 'offline' };
let CONTROL_PENDING = null;
let CONTROL_STARTED = null;
let CONTROL_NOTICE = '';
let CONTROL_NOTICE_KIND = 'info';
let CONTROL_OFFLINE_SINCE = null;
let LAST_CONTROL_ANNOUNCEMENT = '';

let EVENTS = [];
let EVENTS_ERROR = '';
let CONTROL_TIMER = null;
let EVENTS_TIMER = null;
let LOG_REFRESH_TIMER = null;
let LAST_INSTANCE_SIGNATURE = '';

const CONTROL_TERMINAL_OUTCOMES = new Set(['completed', 'passed', 'rejected', 'failed', 'stopped', 'paused', 'resumed', 'no-op']);
const CONTROL_QUEUE_TIMEOUT_MS = 45_000;
const CONTROL_OPERATION_TIMEOUT_MS = 5 * 60_000;
const CONTROL_OFFLINE_GRACE_MS = 5_000;

const PLAN_GROUPS = [
  {
    id: 'match',
    label: 'Match',
    description: 'Choose the battle route, deployment routine, script, and active Heroes.',
    sections: ['destination', 'heroes'],
  },
  {
    id: 'runtime',
    label: 'Runtime',
    description: 'Bind the selected emulator instance and decide how the active army is prepared.',
    sections: ['environment', 'army'],
  },
  {
    id: 'targets',
    label: 'Targets',
    description: 'Set base filters, run limits, and resource goals.',
    sections: ['search', 'limits', 'resources'],
  },
  {
    id: 'between',
    label: 'Between battles',
    description: 'Control donations, recurring work, upgrades, account rotation, and notifications.',
    sections: ['donate', 'events', 'maintenance', 'notify'],
  },
  {
    id: 'advanced',
    label: 'Advanced',
    description: 'Tune emulator pacing and explicitly authorize diagnostic work.',
    sections: ['pacing', 'diagnostics'],
  },
];

const CAPABILITY_GROUPS = [
  {
    label: 'Farming and battles',
    ids: ['battle.regular-ranked-split', 'battle.revenge', 'battle.legend-tiers', 'battle.fast-forward'],
  },
  {
    label: 'Army and Heroes',
    ids: ['army.training', 'army.recipes', 'army.cookbook', 'heroes.six-slot-layout', 'heroes.dragon-duke', 'heroes.hero-journey'],
  },
  {
    label: 'Home Village',
    ids: ['village.collectors', 'village.donations', 'village.upgrades-home', 'village.laboratory', 'village.town-hall-18', 'village.guardians'],
  },
  {
    label: 'Builder Base and Capital',
    ids: ['builder-base.upgrades', 'builder-base.battles', 'builder-base.additional-builder', 'clan-capital.upgrades'],
  },
  {
    label: 'Events, accounts, and recovery',
    ids: ['events.clan-games', 'orchestration.multi-account', 'orchestration.account-queue', 'runtime.recovery', 'chat.global-chat'],
  },
];

const $ = id => document.getElementById(id);
const settingsOf = section => section?.settings || [];
const allSettings = () => (META?.sections || []).flatMap(settingsOf);
const findSetting = id => allSettings().find(setting => setting.id === id);
const optionOf = (setting, value) => (setting?.options || []).find(option => option.value === value);
const asList = value => Array.isArray(value) ? value : (value === '' || value == null ? [] : [value]);
const defaultFor = setting => setting.type === 'multi-select' ? asList(setting.default) : setting.default;
const same = (left, right) => JSON.stringify(left ?? null) === JSON.stringify(right ?? null);
const isChanged = setting => !same(PLAN[setting.id], defaultFor(setting));
const isUnsaved = setting => !same(PLAN[setting.id], SAVED[setting.id]);
const presetItems = () => META?.presets?.items || [];
const presetById = id => presetItems().find(preset => preset.id === id);
const clone = value => structuredClone(value);

function readThemeChoice() {
  try {
    const value = localStorage.getItem('my-bot-theme');
    return ['system', 'light', 'dark'].includes(value) ? value : 'system';
  } catch {
    return 'system';
  }
}

function applyTheme(choice, persist = true) {
  const selected = ['system', 'light', 'dark'].includes(choice) ? choice : 'system';
  if (selected === 'system') delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = selected;
  $('themeSelect').value = selected;
  if (persist) {
    try { localStorage.setItem('my-bot-theme', selected); } catch { /* local storage is optional */ }
  }
}

applyTheme(readThemeChoice(), false);
$('themeSelect').onchange = event => applyTheme(event.target.value);

function groupForSetting(settingId) {
  const section = (META?.sections || []).find(item => settingsOf(item).some(setting => setting.id === settingId));
  return PLAN_GROUPS.find(group => group.sections.includes(section?.id))?.id || 'match';
}

function selectedHeroLabels(plan = PLAN) {
  const setting = findSetting('run.heroes');
  return asList(plan?.['run.heroes']).map(id => optionOf(setting, id)?.label || id);
}

function presetMatchesPlan(preset, plan = PLAN) {
  return !!preset && Object.entries(preset.values || {}).every(([id, value]) => same(plan?.[id], value));
}

function matchingPresetForPlan(plan = PLAN) {
  return presetItems().find(preset => presetMatchesPlan(preset, plan));
}

function setView(view, { updateHash = false, focusHeading = false } = {}) {
  if (!VIEW_IDS.includes(view)) view = 'run';
  ACTIVE_VIEW = view;
  for (const name of VIEW_IDS) {
    const panel = $(`view${name[0].toUpperCase()}${name.slice(1)}`);
    const button = $(`view${name[0].toUpperCase()}${name.slice(1)}Button`);
    panel.hidden = name !== view;
    if (name === view) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  }
  if (updateHash) {
    const next = view === 'plan' ? `#plan/${ACTIVE_GROUP}` : `#${view}`;
    if (location.hash !== next) location.hash = next;
  }
  if (focusHeading && BOOT_READY) {
    const heading = $(`${view}Title`);
    heading?.focus();
  }
}

function setGroup(groupId, { updateHash = false, focusGroup = false } = {}) {
  if (!PLAN_GROUPS.some(group => group.id === groupId)) groupId = 'match';
  ACTIVE_GROUP = groupId;
  updatePlanGroupNav();
  if (FILTER) {
    const target = $(`searchGroup_${groupId}`);
    if (focusGroup && target) {
      target.scrollIntoView({ block: 'start' });
      target.focus();
    }
  } else {
    drawPlanPanel();
  }
  if (updateHash) {
    const next = `#plan/${ACTIVE_GROUP}`;
    if (location.hash !== next) location.hash = next;
  }
}

function applyLocation() {
  const [viewToken, groupToken] = location.hash.replace(/^#/, '').split('/');
  const view = VIEW_IDS.includes(viewToken) ? viewToken : 'run';
  if (groupToken && PLAN_GROUPS.some(group => group.id === groupToken)) ACTIVE_GROUP = groupToken;
  setView(view);
  if (BOOT_READY && view === 'plan') setGroup(ACTIVE_GROUP);
}

function handleRovingKeys(event, buttons) {
  const keys = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'];
  if (!keys.includes(event.key)) return;
  event.preventDefault();
  const current = buttons.indexOf(event.currentTarget);
  let next = current;
  if (event.key === 'Home') next = 0;
  else if (event.key === 'End') next = buttons.length - 1;
  else if (['ArrowRight', 'ArrowDown'].includes(event.key)) next = (current + 1) % buttons.length;
  else next = (current - 1 + buttons.length) % buttons.length;
  buttons[next].focus();
}

const viewButtons = Array.from(document.querySelectorAll('.view-nav button[data-view]'));
for (const button of viewButtons) {
  button.onclick = () => setView(button.dataset.view, { updateHash: true, focusHeading: true });
  button.onkeydown = event => handleRovingKeys(event, viewButtons);
}
$('editPlan').onclick = () => setView('plan', { updateHash: true, focusHeading: true });
$('openDiagnostics').onclick = () => setView('activity', { updateHash: true, focusHeading: true });
window.addEventListener('hashchange', applyLocation);

function initializePlanGroupNav() {
  const nav = $('planGroupNav');
  nav.replaceChildren();
  for (const group of PLAN_GROUPS) {
    const button = document.createElement('button');
    button.type = 'button';
    button.id = `planGroup_${group.id}`;
    button.dataset.group = group.id;
    const label = document.createElement('span');
    label.textContent = group.label;
    const count = document.createElement('span');
    count.className = 'group-count';
    count.setAttribute('aria-hidden', 'true');
    button.append(label, count);
    button.onclick = () => setGroup(group.id, { updateHash: true, focusGroup: true });
    nav.append(button);
  }
  const buttons = Array.from(nav.querySelectorAll('button'));
  for (const button of buttons) button.onkeydown = event => handleRovingKeys(event, buttons);
  updatePlanGroupNav();
}

function groupSettings(group) {
  return group.sections.flatMap(sectionId => settingsOf((META?.sections || []).find(section => section.id === sectionId)));
}

function updatePlanGroupNav() {
  if (!META) return;
  for (const group of PLAN_GROUPS) {
    const button = $(`planGroup_${group.id}`);
    if (!button) continue;
    const total = FILTER ? groupSettings(group).filter(matches).length : groupSettings(group).filter(isChanged).length;
    const count = button.querySelector('.group-count');
    count.textContent = total ? String(total) : '';
    button.setAttribute('aria-label', FILTER
      ? `${group.label}, ${total} search result${total === 1 ? '' : 's'}`
      : `${group.label}${total ? `, ${total} changed` : ''}`);
    if (group.id === ACTIVE_GROUP) button.setAttribute('aria-current', 'page');
    else button.removeAttribute('aria-current');
  }
}

function initializePresets() {
  const select = $('presetSelect');
  select.replaceChildren();
  const custom = document.createElement('option');
  custom.value = 'custom';
  custom.textContent = 'Custom plan — your settings';
  select.append(custom);
  for (const preset of presetItems()) {
    const item = document.createElement('option');
    item.value = preset.id;
    const script = String(preset.values?.['run.attack_script'] || 'Standard').replace(/^\[[^\]]+\][\s_-]*/, '');
    item.textContent = `TH ${preset.town_hall}: ${script === 'profile-current' ? 'Standard' : script}`;
    select.append(item);
  }
  const matched = matchingPresetForPlan();
  SELECTED_PRESET = matched?.id || 'custom';
  select.value = SELECTED_PRESET;
  select.onchange = () => {
    SELECTED_PRESET = select.value;
    if (SELECTED_PRESET === 'custom') {
      renderPresetPreview();
      announcePreset('Custom plan selected. The visible settings were not changed.');
    } else {
      applySelectedPreset();
    }
  };
  renderPresetPreview();
}

function markPresetCustom(settingId = '') {
  LOADED_SAFETY_PATCH = null;
  const preserved = new Set(META?.presets?.preserved_settings || []);
  if (settingId && preserved.has(settingId)) {
    renderPresetPreview();
    return;
  }
  if (SELECTED_PRESET === 'custom') return;
  SELECTED_PRESET = 'custom';
  $('presetSelect').value = 'custom';
}

function announcePreset(text) {
  if ($('presetAnnouncement').textContent === text) return;
  $('presetAnnouncement').textContent = text;
}

function formatSettingValue(setting, value) {
  if (!setting) return String(value ?? '');
  if (setting.type === 'boolean') return value ? 'On' : 'Off';
  if (setting.type === 'multi-select') {
    const labels = asList(value).map(id => optionOf(setting, id)?.label || id);
    return labels.length ? labels.join(', ') : 'None';
  }
  if (setting.type === 'select') return optionOf(setting, value)?.label || String(value ?? '');
  if (value === '' || value == null) return 'Blank';
  return `${value}${setting.unit ? ` ${setting.unit}` : ''}`;
}

function presetChanges(preset) {
  return settingChanges(preset.values || {}, new Set(META?.presets?.preserved_settings || []));
}

function settingChanges(values, preserved = new Set()) {
  return (META?.sections || []).flatMap(section => settingsOf(section)
    .filter(setting => Object.prototype.hasOwnProperty.call(values, setting.id)
      && !preserved.has(setting.id)
      && !same(PLAN[setting.id], values[setting.id]))
    .map(setting => ({ section, setting, before: PLAN[setting.id], after: values[setting.id] })));
}

function buildPresetDiff(changes) {
  const details = document.createElement('details');
  details.className = 'preset-diff';
  const summary = document.createElement('summary');
  summary.textContent = changes.length
    ? `Review ${changes.length} loaded change${changes.length === 1 ? '' : 's'}`
    : 'This starting point already matches the visible plan';
  details.append(summary);
  if (!changes.length) return details;

  const groups = new Map();
  for (const change of changes) {
    if (!groups.has(change.section.id)) groups.set(change.section.id, { section: change.section, changes: [] });
    groups.get(change.section.id).changes.push(change);
  }
  for (const group of groups.values()) {
    const section = document.createElement('section');
    section.className = 'preset-diff-group';
    const heading = document.createElement('strong');
    heading.textContent = group.section.title;
    const list = document.createElement('dl');
    for (const change of group.changes) {
      const row = document.createElement('div');
      const label = document.createElement('dt');
      label.textContent = change.setting.label;
      const values = document.createElement('dd');
      const before = document.createElement('del');
      before.textContent = formatSettingValue(change.setting, change.before);
      const separator = document.createTextNode(' to ');
      const after = document.createElement('ins');
      after.textContent = formatSettingValue(change.setting, change.after);
      values.append(before, separator, after);
      row.append(label, values);
      list.append(row);
    }
    section.append(heading, list);
    details.append(section);
  }
  return details;
}

function addPresetFacts(preview, plan) {
  const facts = document.createElement('span');
  facts.className = 'preset-facts';
  const scriptSetting = findSetting('run.attack_script');
  const script = optionOf(scriptSetting, plan['run.attack_script']);
  const heroes = selectedHeroLabels(plan);
  const townHall = Number(plan['run.town_hall'] || 0);
  for (const value of [
    `Town Hall: ${townHall > 0 ? `TH${townHall}` : 'detect at Start'}`,
    `Script: ${script?.label || plan['run.attack_script'] || 'Profile selection'}`,
    `Heroes: ${heroes.length ? heroes.join(', ') : 'none'}`,
    `Limit: ${plan['run.max_battles'] || 0} battles / ${plan['run.duration_minutes'] || 0} min`,
  ]) {
    const fact = document.createElement('span');
    fact.textContent = value;
    facts.append(fact);
  }
  preview.append(facts);
}

function renderPresetPreview(loadedChanges = null) {
  const preview = $('presetPreview');
  preview.replaceChildren();
  const preset = presetById(SELECTED_PRESET);
  if (!preset) {
    const title = document.createElement('strong');
    title.textContent = 'Custom plan';
    const note = document.createElement('span');
    note.textContent = 'These are the visible values. Applying writes them; selecting a Town Hall replaces every setting owned by that starting point.';
    preview.append(title, note);
    addPresetFacts(preview, PLAN);
    if (LOADED_SAFETY_PATCH) {
      const safety = document.createElement('span');
      safety.className = 'preset-note';
      safety.textContent = `${LOADED_SAFETY_PATCH.label} loaded ${LOADED_SAFETY_PATCH.changes.length} visible change${LOADED_SAFETY_PATCH.changes.length === 1 ? '' : 's'}. Runtime and diagnostic acknowledgement stayed unchanged. Nothing was saved or started.`;
      preview.append(safety, buildPresetDiff(LOADED_SAFETY_PATCH.changes));
    }
    const heroes = selectedHeroLabels();
    const heroNote = document.createElement('span');
    heroNote.className = 'preset-note';
    heroNote.textContent = heroes.length
      ? 'Selected Heroes deploy only when their attack-bar slots are present. This does not open Hero Hall.'
      : 'No Heroes are selected for deployment.';
    preview.append(heroNote);
    return;
  }

  const changes = loadedChanges ?? presetChanges(preset);
  const title = document.createElement('strong');
  title.textContent = changes.length
    ? `${preset.label}: ${changes.length} field${changes.length === 1 ? '' : 's'} loaded`
    : `${preset.label}: visible plan matches`;
  const description = document.createElement('span');
  description.textContent = preset.description;
  preview.append(title, description);
  addPresetFacts(preview, preset.values || PLAN);
  const basis = document.createElement('span');
  basis.className = 'preset-basis';
  basis.textContent = `Basis: ${preset.source_note}`;
  const safety = document.createElement('span');
  safety.textContent = 'The changes remain unsaved until Apply plan. Start remains a separate action.';
  preview.append(basis, buildPresetDiff(changes), safety);
}

function applySelectedPreset() {
  const preset = presetById(SELECTED_PRESET);
  if (!preset) return;
  LOADED_SAFETY_PATCH = null;
  const changes = presetChanges(preset);
  const preserved = new Set(META?.presets?.preserved_settings || []);
  for (const [id, value] of Object.entries(preset.values || {})) {
    if (!findSetting(id) || preserved.has(id)) continue;
    PLAN[id] = clone(value);
  }
  drawPlanPanel();
  updatePlanGroupNav();
  renderPresetPreview(changes);
  renderPlanReceipts();
  updateDirty();
  announcePreset(`${preset.label} loaded ${changes.length} unsaved change${changes.length === 1 ? '' : 's'}.`);
  setSaveStatus(`${preset.label} is visible but not applied.`, 'warn');
}

function applyStrategySafetyPatch(strategyId) {
  const patch = STRATEGY_SAFETY_PATCHES[strategyId];
  if (!patch) return false;
  const preserved = new Set(META?.presets?.preserved_settings || []);
  const changes = settingChanges(patch.values, preserved);
  markPresetCustom();
  for (const [id, value] of Object.entries(patch.values)) {
    if (!findSetting(id) || preserved.has(id)) continue;
    PLAN[id] = clone(value);
  }
  LOADED_SAFETY_PATCH = { label: patch.label, changes };
  drawPlanPanel();
  updatePlanGroupNav();
  renderPresetPreview();
  renderPlanReceipts();
  updateDirty();
  announcePreset(`${patch.label} loaded ${changes.length} unsaved change${changes.length === 1 ? '' : 's'}.`);
  setSaveStatus(`${patch.label} are visible but not applied. Review diagnostic acknowledgement, then Apply plan.`, 'warn');
  return true;
}

function matches(setting) {
  if (!FILTER) return true;
  const optionText = (setting.options || []).flatMap(option => [
    option.label,
    option.summary,
    option.description,
    option.disabled_reason,
  ]);
  return [setting.label, setting.summary, setting.description, setting.id, ...optionText]
    .some(text => String(text ?? '').toLocaleLowerCase().includes(FILTER));
}

function createEditorHeading(title, description, id = '') {
  const heading = document.createElement('div');
  heading.className = 'editor-heading';
  const h3 = document.createElement('h3');
  h3.textContent = title;
  if (id) {
    h3.id = id;
    h3.tabIndex = -1;
  }
  const p = document.createElement('p');
  p.textContent = description;
  heading.append(h3, p);
  return heading;
}

function drawPlanPanel() {
  const panel = $('panel');
  panel.replaceChildren();
  if (!META) return;

  if (FILTER) {
    const heading = createEditorHeading('Search results', `Matches for “${$('filter').value.trim()}” across all five plan groups.`);
    heading.classList.add('search-heading');
    panel.append(heading);
    let resultCount = 0;
    for (const group of PLAN_GROUPS) {
      const sections = group.sections
        .map(id => (META.sections || []).find(section => section.id === id))
        .filter(Boolean)
        .map(section => ({ section, settings: settingsOf(section).filter(matches) }))
        .filter(item => item.settings.length);
      if (!sections.length) continue;
      resultCount += sections.reduce((total, item) => total + item.settings.length, 0);
      const groupSection = document.createElement('section');
      groupSection.className = 'search-group';
      const groupHeading = document.createElement('h3');
      groupHeading.id = `searchGroup_${group.id}`;
      groupHeading.tabIndex = -1;
      groupHeading.textContent = group.label;
      groupSection.append(groupHeading);
      for (const item of sections) groupSection.append(renderMetadataSection(item.section, item.settings));
      panel.append(groupSection);
    }
    if (!resultCount) {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = 'No setting or option matches this search.';
      panel.append(empty);
    }
  } else {
    const group = PLAN_GROUPS.find(item => item.id === ACTIVE_GROUP) || PLAN_GROUPS[0];
    panel.append(createEditorHeading(group.label, group.description, 'activeGroupHeading'));
    for (const sectionId of group.sections) {
      const section = (META.sections || []).find(item => item.id === sectionId);
      if (section) panel.append(renderMetadataSection(section, settingsOf(section)));
    }
  }
  updatePlanGroupNav();
}

function renderMetadataSection(section, settings) {
  const container = document.createElement('section');
  container.className = 'metadata-section';
  container.dataset.section = section.id;
  const heading = document.createElement('h4');
  heading.textContent = section.title;
  const description = document.createElement('p');
  description.textContent = section.description;
  container.append(heading, description);
  for (const setting of settings) container.append(renderRow(setting));
  return container;
}

function settingCondition(setting) {
  const id = setting.id;
  if (['planned', 'unsupported'].includes(setting.availability)
      && same(PLAN[id], defaultFor(setting))) {
    return { disabled: true, message: setting.disabled_reason || 'This setting is unavailable in the current build.' };
  }
  if (id === 'run.attack_script' && PLAN['run.strategy'] !== 'legacy.csv') {
    if (PLAN[id] === 'profile-current') {
      return { disabled: true, message: 'Standard and Smart deployment use the active profile; named CSV selection is inactive.' };
    }
    return { disabled: false, message: 'This combination cannot be applied. Choose “Use profile selection” or switch to Scripted deployment.' };
  }
  if (id === 'run.diagnostic_note' && !PLAN['run.diagnostic_mode']) {
    return { disabled: true, message: 'Turn on Allow unverified before recording a supervised diagnostic acknowledgement.' };
  }
  if (id === 'runtime.instance' && PLAN['runtime.emulator'] === 'auto' && !String(PLAN[id] || '').trim()) {
    return { disabled: true, message: 'Choose a specific emulator before selecting an instance.' };
  }
  if (['army.train_spells', 'army.train_sieges'].includes(id) && !PLAN['army.manage_training'] && !PLAN[id]) {
    return { disabled: true, message: 'This setting is inactive while Manage training is off.' };
  }
  if (id === 'pacing.break_minutes' && Number(PLAN['pacing.break_every_minutes'] || 0) === 0) {
    return { disabled: true, message: 'Scheduled rests are off, so the rest length is inactive.' };
  }
  if (id === 'notify.channel' && !PLAN['notify.on_stop'] && !PLAN['notify.on_error']
      && PLAN[id] === defaultFor(setting)) {
    return { disabled: true, message: 'Choose a notification trigger before selecting a channel.' };
  }
  return { disabled: false, message: '' };
}

function renderRow(setting) {
  const row = document.createElement('div');
  row.className = 'setting-row';
  row.id = `row_${setting.id}`;
  row.dataset.setting = setting.id;
  row.classList.toggle('is-changed', isChanged(setting));
  const condition = settingCondition(setting);
  row.classList.toggle('is-inactive', condition.disabled);

  const heading = document.createElement('div');
  heading.className = 'row-label';
  const titleLine = document.createElement('div');
  titleLine.className = 'row-title';
  const label = document.createElement(setting.type === 'multi-select' ? 'span' : 'label');
  label.id = `l_${setting.id}`;
  if (setting.type !== 'multi-select') label.htmlFor = `f_${setting.id}`;
  label.textContent = setting.label;
  if (setting.required) {
    const required = document.createElement('span');
    required.className = 'required-mark';
    required.textContent = ' required';
    label.append(required);
  }
  titleLine.append(label);
  if (isChanged(setting)) {
    const revert = document.createElement('button');
    revert.className = 'revert';
    revert.type = 'button';
    revert.id = `r_${setting.id}`;
    revert.textContent = 'Use default';
    revert.onclick = () => {
      PLAN[setting.id] = clone(defaultFor(setting));
      markPresetCustom(setting.id);
      refreshAfterChange(setting, revert.id);
    };
    titleLine.append(revert);
  }
  const summary = document.createElement('span');
  summary.className = 'row-summary';
  summary.id = `s_${setting.id}`;
  summary.textContent = setting.summary;
  heading.append(titleLine, summary);

  const field = document.createElement('div');
  field.className = 'field';
  if (setting.type === 'multi-select') {
    field.setAttribute('role', 'group');
    field.setAttribute('aria-labelledby', label.id);
    field.setAttribute('aria-describedby', summary.id);
    if (setting.required) field.setAttribute('aria-required', 'true');
  }
  buildField(setting, field, condition);
  field.append(buildSettingHelp(setting));
  row.append(heading, field);
  return row;
}

function buildField(setting, field, condition) {
  if (setting.type === 'multi-select') {
    buildChips(setting, field);
    if (condition.message) appendFieldMessage(setting, field, condition.message);
    return;
  }

  const control = makeControl(setting);
  control.id = `f_${setting.id}`;
  const nativeFixed = Object.prototype.hasOwnProperty.call(setting, 'native_fixed_value');
  control.disabled = nativeFixed || condition.disabled;
  if (setting.required) {
    control.required = true;
    control.setAttribute('aria-required', 'true');
  }
  const descriptions = [`s_${setting.id}`];
  if (nativeFixed || condition.message) descriptions.push(`m_${setting.id}`);
  control.setAttribute('aria-describedby', descriptions.join(' '));
  control.onchange = () => {
    PLAN[setting.id] = readControl(setting, control);
    if (setting.id === 'run.strategy' && applyStrategySafetyPatch(PLAN[setting.id])) return;
    if (PLAN['run.strategy'] === 'home.collectors' && PLAN[setting.id] === true
        && setting.id === 'events.collect_resources') PLAN['events.collect_loot_cart'] = false;
    if (PLAN['run.strategy'] === 'home.collectors' && PLAN[setting.id] === true
        && setting.id === 'events.collect_loot_cart') PLAN['events.collect_resources'] = false;
    markPresetCustom(setting.id);
    refreshAfterChange(setting, control.id);
  };

  if (setting.type === 'boolean') {
    const wrap = document.createElement('span');
    wrap.className = 'switch';
    const track = document.createElement('span');
    track.className = 'switch-track';
    const knob = document.createElement('span');
    knob.className = 'switch-knob';
    wrap.append(control, track, knob);
    field.append(wrap);
  } else {
    field.append(control);
    if (setting.unit) {
      const unit = document.createElement('span');
      unit.className = 'unit';
      unit.textContent = setting.unit;
      field.append(unit);
    }
  }

  if (nativeFixed) appendFieldMessage(setting, field, setting.native_fixed_reason, 'fixed');
  else if (condition.message) appendFieldMessage(setting, field, condition.message);
}

function appendFieldMessage(setting, field, text, kind = '') {
  const message = document.createElement('p');
  message.id = `m_${setting.id}`;
  message.className = `field-message ${kind}`.trim();
  message.textContent = text;
  field.append(message);
}

function makeControl(setting) {
  if (setting.type === 'boolean') {
    const control = document.createElement('input');
    control.type = 'checkbox';
    control.checked = !!PLAN[setting.id];
    return control;
  }
  if (setting.type === 'integer') {
    const control = document.createElement('input');
    control.type = 'number';
    const rules = setting.validation || {};
    if (rules.minimum !== undefined) control.min = rules.minimum;
    if (rules.maximum !== undefined) control.max = rules.maximum;
    if (rules.step !== undefined) control.step = rules.step;
    control.value = PLAN[setting.id] ?? defaultFor(setting) ?? 0;
    return control;
  }
  if (setting.type === 'instance-select') {
    const control = document.createElement('select');
    const blank = document.createElement('option');
    blank.value = '';
    blank.textContent = PLAN['runtime.emulator'] === 'auto'
      ? 'Automatic single-instance detection'
      : 'Select the attached instance';
    control.append(blank);
    const values = new Set();
    const planned = String(PLAN[setting.id] || '').trim();
    const attached = String(CONTROL.instance || '').trim();
    if (planned) values.add(planned);
    if (attached) values.add(attached);
    for (const value of values) {
      const option = document.createElement('option');
      option.value = value;
      option.textContent = value === attached ? `${value} (attached)` : value;
      control.append(option);
    }
    control.value = planned;
    return control;
  }
  if ((setting.options || []).length) {
    const control = document.createElement('select');
    for (const item of setting.options) {
      const option = document.createElement('option');
      option.value = item.value;
      option.textContent = item.label;
      if (item.recommended) option.textContent += ' (recommended)';
      if (['planned', 'unsupported'].includes(item.availability)) {
        option.textContent += ' — unavailable';
        option.disabled = true;
      }
      control.append(option);
    }
    control.value = PLAN[setting.id] ?? defaultFor(setting);
    return control;
  }
  const control = document.createElement('input');
  control.type = 'text';
  control.value = PLAN[setting.id] ?? '';
  control.placeholder = setting.empty_state || '';
  if (setting.validation?.max_length) control.maxLength = setting.validation.max_length;
  return control;
}

function readControl(setting, control) {
  if (setting.type === 'boolean') return control.checked;
  if (setting.type === 'integer') return control.value === '' ? 0 : Number(control.value);
  return control.value;
}

function buildChips(setting, field) {
  const chosen = asList(PLAN[setting.id]);
  const max = setting.max_selected || setting.options.length;
  const plannedTownHall = Number(PLAN['run.town_hall'] || 0);
  const chips = document.createElement('div');
  chips.className = 'chips';
  for (const option of setting.options) {
    const selected = chosen.includes(option.value);
    const chip = document.createElement('button');
    chip.type = 'button';
    chip.className = 'chip';
    chip.textContent = option.label;
    chip.id = `f_${setting.id}_${option.value}`;
    chip.setAttribute('aria-pressed', String(selected));
    chip.setAttribute('aria-describedby', `s_${setting.id}`);
    const unavailable = ['planned', 'unsupported'].includes(option.availability);
    const lockedForTownHall = setting.id === 'run.heroes' && plannedTownHall > 0
      && Number(option.unlock_town_hall || 0) > plannedTownHall;
    chip.disabled = !selected && (chosen.length >= max || unavailable || lockedForTownHall);
    chip.onclick = () => {
      const next = asList(PLAN[setting.id]);
      const index = next.indexOf(option.value);
      if (index >= 0) next.splice(index, 1);
      else if (next.length < max) next.push(option.value);
      PLAN[setting.id] = next;
      markPresetCustom(setting.id);
      refreshAfterChange(setting, chip.id);
    };
    chips.append(chip);
  }
  field.append(chips);
  const slots = document.createElement('span');
  slots.className = 'slots';
  slots.textContent = `${chosen.length} of ${max} slots selected`;
  field.append(slots);
}

function evidenceText(option) {
  if (!option) return '';
  if (['planned', 'unsupported'].includes(option.availability)) return 'Unavailable in this build.';
  if (option.runtime_verified) return 'Confirmed: a supervised run issued and observed this route. Results do not establish strategy quality.';
  if (option.availability === 'gated') return 'Planned and implemented; issued actions still need fresh supervised confirmation.';
  return 'Planned and implemented; no separate confirmed run is recorded for this option.';
}

function appendEvidenceDetails(body, evidenceOwner, label = '') {
  if (!evidenceOwner?.availability) return;
  const evidence = document.createElement('p');
  evidence.className = 'evidence-line';
  evidence.textContent = `${label ? `${label}: ` : ''}${evidenceText(evidenceOwner)}`;
  body.append(evidence);
  if ((evidenceOwner.prerequisites || []).length) {
    const list = document.createElement('ul');
    for (const prerequisite of evidenceOwner.prerequisites) {
      const item = document.createElement('li');
      item.textContent = prerequisite;
      list.append(item);
    }
    body.append(list);
  }
  if (evidenceOwner.disabled_reason) {
    const reason = document.createElement('p');
    reason.textContent = `Current limit: ${evidenceOwner.disabled_reason}`;
    body.append(reason);
  }
  if (evidenceOwner.warning) {
    const warning = document.createElement('p');
    warning.textContent = `Note: ${evidenceOwner.warning}`;
    body.append(warning);
  }
}

function buildSettingHelp(setting) {
  const details = document.createElement('details');
  details.className = 'setting-help';
  const summary = document.createElement('summary');
  summary.textContent = 'Details and evidence';
  const body = document.createElement('div');
  body.className = 'setting-help-body';
  const description = document.createElement('p');
  description.textContent = setting.description;
  body.append(description);
  appendEvidenceDetails(body, setting, setting.label);

  const selectedOptions = setting.type === 'multi-select'
    ? asList(PLAN[setting.id]).map(value => optionOf(setting, value)).filter(Boolean)
    : [optionOf(setting, PLAN[setting.id])].filter(Boolean);
  for (const option of selectedOptions) {
    const optionDescription = document.createElement('p');
    const name = document.createElement('strong');
    name.textContent = `${option.label}: `;
    optionDescription.append(name, document.createTextNode(option.description));
    body.append(optionDescription);
    appendEvidenceDetails(body, option);
  }
  if (setting.native_fixed_reason) {
    const fixed = document.createElement('p');
    fixed.textContent = `Native constraint: ${setting.native_fixed_reason}`;
    body.append(fixed);
  }
  details.append(summary, body);
  return details;
}

function refreshAfterChange(setting, focusId = '') {
  drawPlanPanel();
  updatePlanGroupNav();
  renderPresetPreview();
  renderPlanReceipts();
  updateDirty();
  if (focusId) {
    const fallback = setting.type === 'multi-select'
      ? document.querySelector(`[id^="f_${setting.id}_"]`)
      : $(`f_${setting.id}`);
    (document.getElementById(focusId) || fallback)?.focus();
  }
}

function addProblem(problems, message, settingId) {
  if (!problems.some(problem => problem.message === message)) {
    problems.push({ message, settingId, groupId: groupForSetting(settingId) });
  }
}

function clientProblems(plan = PLAN) {
  if (!META) return [{ message: 'Planner metadata is not loaded.', settingId: '', groupId: 'match' }];
  const problems = [];
  for (const setting of allSettings()) {
    const value = plan[setting.id];
    const emptyRequired = setting.required && (value == null || value === '' || (Array.isArray(value) && value.length === 0));
    if (emptyRequired) addProblem(problems, `${setting.label} is required.`, setting.id);
    if (setting.type === 'integer') {
      const number = Number(value);
      const rules = setting.validation || {};
      if (!Number.isFinite(number) || !Number.isInteger(number)) addProblem(problems, `${setting.label} must be a whole number.`, setting.id);
      else if (rules.minimum !== undefined && number < rules.minimum) addProblem(problems, `${setting.label} cannot be below ${rules.minimum}.`, setting.id);
      else if (rules.maximum !== undefined && number > rules.maximum) addProblem(problems, `${setting.label} cannot exceed ${rules.maximum}.`, setting.id);
      else if (rules.step !== undefined && (number - Number(rules.minimum || 0)) % rules.step !== 0) {
        addProblem(problems, `${setting.label} must use increments of ${rules.step}.`, setting.id);
      }
    }
    if (['instance-select', 'text', 'profile-queue'].includes(setting.type)) {
      if (typeof value !== 'string') addProblem(problems, `${setting.label} must be text.`, setting.id);
      else if (setting.validation?.max_length !== undefined && value.length > setting.validation.max_length) {
        addProblem(problems, `${setting.label} cannot exceed ${setting.validation.max_length} characters.`, setting.id);
      }
    }
    if (setting.type === 'select') {
      const option = optionOf(setting, value);
      if (!option) addProblem(problems, `${setting.label} does not name a current option.`, setting.id);
      else if (['planned', 'unsupported'].includes(option.availability)) addProblem(problems, `${option.label} is unavailable in this build.`, setting.id);
      else if (option.availability === 'gated' && !plan['run.diagnostic_mode']) {
        addProblem(problems, `${option.label} needs Allow unverified and a supervised diagnostic acknowledgement.`, setting.id);
      }
    }
    if (setting.type === 'multi-select') {
      const selected = asList(value);
      if (selected.length > setting.max_selected) addProblem(problems, `${setting.label} allows at most ${setting.max_selected} selections.`, setting.id);
      for (const selectedValue of selected) {
        const option = optionOf(setting, selectedValue);
        if (!option) addProblem(problems, `${setting.label} contains an unknown selection.`, setting.id);
        else if (['planned', 'unsupported'].includes(option.availability)) addProblem(problems, `${option.label} is unavailable in this build.`, setting.id);
        else if (option.availability === 'gated' && !plan['run.diagnostic_mode']) {
          addProblem(problems, `${option.label} needs Allow unverified and a supervised diagnostic acknowledgement.`, setting.id);
        }
      }
    }
    if (Object.prototype.hasOwnProperty.call(setting, 'native_fixed_value') && !same(value, setting.native_fixed_value)) {
      addProblem(problems, `${setting.label} must keep the native fixed value.`, setting.id);
    }
    const settingEvidenceActive = setting.availability && !same(value, setting.default);
    if (settingEvidenceActive && ['planned', 'unsupported'].includes(setting.availability)) {
      addProblem(problems, `${setting.label} is unavailable in this build.`, setting.id);
    } else if (settingEvidenceActive && setting.availability === 'gated' && !plan['run.diagnostic_mode']) {
      addProblem(problems, `${setting.label} needs Allow unverified and a supervised diagnostic acknowledgement.`, setting.id);
    }
  }

  if (plan['run.surface'] !== 'regular') addProblem(problems, 'Only Regular Battles can start through the native engine.', 'run.surface');
  const homeMaintenance = plan['run.strategy'] === 'home.collectors';
  const clanRequestOnly = plan['run.strategy'] === 'home.clan-request';
  if (!['legacy.csv', 'legacy.standard', 'smart.local', 'home.collectors', 'home.clan-request'].includes(plan['run.strategy'])) {
    addProblem(problems, 'The selected deployment routine has no native adapter.', 'run.strategy');
  }
  if (['legacy.csv', 'legacy.standard', 'smart.local'].includes(plan['run.strategy'])) {
    addProblem(problems, 'Battle routes are unavailable in this fork because the inherited ImgLoc runtime rejected exact-current supervised readiness. Licensed permission or a clean-room recognizer is required; Allow unverified cannot bypass this gate.', 'run.strategy');
  }
  if (plan['run.strategy'] !== 'legacy.csv' && plan['run.attack_script'] !== 'profile-current') {
    addProblem(problems, 'Standard and Smart deployment require “Use profile selection.”', 'run.attack_script');
  }
  if (plan['run.strategy'] === 'smart.local' && !plan['run.diagnostic_mode']) {
    addProblem(problems, 'Smart Attack remains a supervised diagnostic option until its deterministic policy has fresh live proof.', 'run.diagnostic_mode');
  }
  const plannedTownHall = Number(plan['run.town_hall'] || 0);
  const heroSetting = findSetting('run.heroes');
  for (const heroId of asList(plan['run.heroes'])) {
    const hero = optionOf(heroSetting, heroId);
    if (!hero?.active_slot_eligible || heroId === 'dragon-duke') {
      addProblem(problems, `${hero?.label || heroId} is not present in the inherited deployment actuator.`, 'run.heroes');
      continue;
    }
    if (plannedTownHall > 0 && Number(hero.unlock_town_hall || 0) > plannedTownHall) {
      addProblem(problems, `${hero.label} unlocks at Town Hall ${hero.unlock_town_hall}, after planned TH${plannedTownHall}.`, 'run.heroes');
    }
  }
  const emulator = String(plan['runtime.emulator'] || '').trim().toLowerCase();
  const instance = String(plan['runtime.instance'] || '').trim();
  if (emulator === 'auto' && instance) addProblem(problems, 'Choose a specific emulator before selecting an instance.', 'runtime.instance');
  if (emulator !== 'auto' && !instance) addProblem(problems, 'Choose the exact emulator instance so capture, input, and docking stay bound to one account.', 'runtime.instance');
  if (plan['army.source'] !== 'recipe' || String(plan['army.recipe_name'] || '').trim()) {
    addProblem(problems, 'The run can use only the active profile army; named recipes are not wired.', 'army.source');
  }
  if (homeMaintenance) {
    if (emulator === 'auto' || !instance) addProblem(problems, 'Home maintenance requires the exact non-Auto emulator and instance.', 'runtime.instance');
    if (instance && !/^[A-Za-z0-9_. -]{1,64}$/.test(instance)) addProblem(problems, 'The Home route instance name contains unsupported characters.', 'runtime.instance');
    if (!plan['run.diagnostic_mode']) addProblem(problems, 'Home maintenance requires supervised diagnostic acknowledgement.', 'run.diagnostic_mode');
    const collectors = plan['events.collect_resources'] === true;
    const dailyReward = plan['events.collect_daily_reward'] === true;
    const lootCart = plan['events.collect_loot_cart'] === true;
    const treasury = plan['events.collect_treasury'] === true;
    const selectedHomeTasks = [collectors, dailyReward, lootCart, treasury].filter(Boolean).length;
    if (selectedHomeTasks !== 1) addProblem(problems, 'Choose exactly one template-free task: collectors, Loot Cart, Treasury, or startup Daily Reward.', 'events.collect_resources');
    if (plan['army.manage_training'] || plan['army.wait_for_full'] || plan['army.train_spells'] || plan['army.train_sieges']) addProblem(problems, 'Home maintenance requires training, army wait, spells, and sieges off.', 'army.manage_training');
    if (asList(plan['run.heroes']).length) addProblem(problems, 'Home maintenance requires no selected Heroes.', 'run.heroes');
    if (Number(plan['run.duration_minutes']) !== 0 || Number(plan['run.max_battles']) !== 0 || plan['run.stop_on_star_bonus'] || Number(plan['run.max_failures']) !== 0) addProblem(problems, 'Home maintenance is one pass; duration, battles, star bonus, and failure limits must be 0/off.', 'run.max_battles');
    if (['target.gold', 'target.elixir', 'target.dark_elixir', 'search.min_gold', 'search.min_elixir', 'search.min_dark', 'search.max_seconds'].some((key) => Number(plan[key]) !== 0)) addProblem(problems, 'Home maintenance cannot configure matchmaking or battle-loot targets.', 'search.min_gold');
    if (plan['donate.mode'] !== 'off' || plan['donate.request_when_short'] || Number(plan['donate.max_per_run']) !== 0) addProblem(problems, 'Home maintenance requires donations and requests off.', 'donate.mode');
    if (plan['events.clan_games'] || Number(plan['events.clan_games_point_cap']) !== 0) addProblem(problems, 'Home maintenance cannot enter Clan Games.', 'events.clan_games');
    if (plan['events.laboratory'] !== 'off') addProblem(problems, 'Home maintenance requires Laboratory off.', 'events.laboratory');
    if (plan['upgrade.policy'] !== 'disabled') addProblem(problems, 'Home maintenance requires upgrades disabled.', 'upgrade.policy');
    if (String(plan['account.queue'] || '').trim()) addProblem(problems, 'Home maintenance cannot rotate accounts.', 'account.queue');
  } else if (clanRequestOnly) {
    if (!plan['run.diagnostic_mode']) addProblem(problems, 'Clan request requires supervised diagnostic acknowledgement.', 'run.diagnostic_mode');
    if (plan['army.manage_training'] || plan['army.wait_for_full'] || plan['army.train_spells'] || plan['army.train_sieges']) addProblem(problems, 'Clan request requires training, army wait, spells, and sieges off.', 'army.manage_training');
    if (asList(plan['run.heroes']).length) addProblem(problems, 'Clan request requires no selected Heroes.', 'run.heroes');
    if (Number(plan['run.duration_minutes']) !== 0 || Number(plan['run.max_battles']) !== 0 || plan['run.stop_on_star_bonus'] || Number(plan['run.max_failures']) !== 0) addProblem(problems, 'Clan request is one pass; duration, battles, star bonus, and failure limits must be 0/off.', 'run.max_battles');
    if (['target.gold', 'target.elixir', 'target.dark_elixir', 'search.min_gold', 'search.min_elixir', 'search.min_dark', 'search.max_seconds'].some((key) => Number(plan[key]) !== 0)) addProblem(problems, 'Clan request cannot configure matchmaking or battle-loot targets.', 'search.min_gold');
    if (plan['donate.mode'] !== 'off' || !plan['donate.request_when_short'] || !plan['donate.keep_army'] || Number(plan['donate.max_per_run']) !== 0) addProblem(problems, 'Clan request requires Off, Request when available on, army preservation on, and donation limit 0.', 'donate.request_when_short');
    if (plan['events.collect_resources'] || plan['events.collect_daily_reward'] || plan['events.collect_loot_cart'] || plan['events.collect_treasury'] || plan['events.clan_games'] || Number(plan['events.clan_games_point_cap']) !== 0) addProblem(problems, 'Clan request cannot collect resources, claim rewards, or enter Clan Games.', 'events.clan_games');
    if (plan['events.laboratory'] !== 'off') addProblem(problems, 'Clan request requires Laboratory off.', 'events.laboratory');
    if (plan['upgrade.policy'] !== 'disabled') addProblem(problems, 'Clan request requires upgrades disabled.', 'upgrade.policy');
    if (String(plan['account.queue'] || '').trim()) addProblem(problems, 'Clan request cannot rotate accounts.', 'account.queue');
    if (Number(plan['pacing.break_every_minutes']) !== 0) addProblem(problems, 'Clan request requires scheduled breaks off.', 'pacing.break_every_minutes');
    if (emulator === 'auto' || !instance) addProblem(problems, 'Clan request requires the exact non-Auto emulator and instance.', 'runtime.instance');
    if (instance && !/^[A-Za-z0-9_. -]{1,64}$/.test(instance)) addProblem(problems, 'The Home route instance name contains unsupported characters.', 'runtime.instance');
  } else if (plan['events.collect_resources'] || plan['events.collect_daily_reward'] || plan['events.collect_loot_cart'] || plan['events.collect_treasury']) {
    addProblem(problems, 'Home collection work requires the Home maintenance strategy.', 'events.collect_resources');
  } else if (plan['army.manage_training']) {
    addProblem(problems, 'Managed training is disabled because the inherited profile training path is not closed-world. Turn it off and use the current trained army for one battle.', 'army.manage_training');
  } else {
    if (Number(plan['run.max_battles']) !== 1) addProblem(problems, 'Current trained army mode requires exactly one battle.', 'run.max_battles');
    if (!plan['army.wait_for_full']) addProblem(problems, 'Current trained army mode requires a fresh full-army check.', 'army.wait_for_full');
    if (plan['donate.mode'] !== 'off') addProblem(problems, 'Donations must be off for the one-shot current army.', 'donate.mode');
    if (plan['donate.request_when_short']) addProblem(problems, 'Current trained army mode cannot request troops.', 'donate.request_when_short');
    if (plan['events.clan_games'] || plan['events.collect_resources'] || plan['events.collect_daily_reward'] || plan['events.collect_loot_cart'] || plan['events.collect_treasury']) addProblem(problems, 'Current trained army mode cannot run event or Home collection work before battle.', 'events.clan_games');
    if (plan['events.laboratory'] !== 'off') addProblem(problems, 'Current trained army mode requires Laboratory off.', 'events.laboratory');
    if (plan['upgrade.policy'] !== 'disabled') addProblem(problems, 'Current trained army mode requires upgrades off.', 'upgrade.policy');
  }
  if (Number(plan['pacing.retry_attempts'] || 0) !== 0) addProblem(problems, 'Generic action retries are not wired; keep retries at zero.', 'pacing.retry_attempts');
  if (plan['run.diagnostic_mode'] && !String(plan['run.diagnostic_note'] || '').trim()) {
    addProblem(problems, 'A supervised diagnostic acknowledgement is required when Allow unverified is on.', 'run.diagnostic_note');
  }
  return problems;
}

function focusSetting(settingId) {
  FILTER = '';
  $('filter').value = '';
  ACTIVE_GROUP = groupForSetting(settingId);
  setView('plan', { updateHash: true });
  drawPlanPanel();
  updatePlanGroupNav();
  const setting = findSetting(settingId);
  const control = setting?.type === 'multi-select'
    ? document.querySelector(`[id^="f_${settingId}_"]`)
    : $(`f_${settingId}`);
  const row = $(`row_${settingId}`);
  const target = control && !control.disabled ? control : row;
  if (target === row) row.tabIndex = -1;
  target?.scrollIntoView({ block: 'center' });
  target?.focus?.();
}

function renderValidation(list, problems, allowNavigation = true) {
  list.replaceChildren();
  if (!problems.length) {
    const item = document.createElement('li');
    item.className = 'ok';
    item.textContent = 'No client-side contract issues.';
    list.append(item);
    return;
  }
  for (const problem of problems) {
    const item = document.createElement('li');
    item.append(document.createTextNode(problem.message));
    if (allowNavigation && problem.settingId) {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = 'Go to setting';
      button.onclick = () => focusSetting(problem.settingId);
      item.append(button);
    }
    list.append(item);
  }
}

function summaryEntries(plan) {
  const surface = optionOf(findSetting('run.surface'), plan['run.surface']);
  const strategy = optionOf(findSetting('run.strategy'), plan['run.strategy']);
  const script = optionOf(findSetting('run.attack_script'), plan['run.attack_script']);
  const heroes = selectedHeroLabels(plan);
  const emulator = optionOf(findSetting('runtime.emulator'), plan['runtime.emulator']);
  const matched = matchingPresetForPlan(plan);
  const plannedTownHall = Number(plan['run.town_hall'] || 0);
  return [
    ['Starting point', matched?.label || 'Custom plan'],
    ['Town Hall', plannedTownHall > 0 ? `TH${plannedTownHall}` : 'Detect at Start'],
    ['Battle', surface?.label || plan['run.surface'] || 'Not selected'],
    ['Deployment', strategy?.label || plan['run.strategy'] || 'Not selected'],
    ['Script', script?.label || plan['run.attack_script'] || 'Not selected'],
    ['Heroes', heroes.length ? heroes.join(', ') : 'None selected'],
    ['Limit', `${plan['run.max_battles'] || 0} battles / ${plan['run.duration_minutes'] || 0} min`],
    ['Emulator', `${emulator?.label || plan['runtime.emulator'] || 'Automatic'}${plan['runtime.instance'] ? ` / ${plan['runtime.instance']}` : ''}`],
  ];
}

function renderSummary(element, plan) {
  element.replaceChildren();
  const list = document.createElement('dl');
  for (const [term, value] of summaryEntries(plan)) {
    const dt = document.createElement('dt');
    dt.textContent = term;
    const dd = document.createElement('dd');
    dd.textContent = value;
    list.append(dt, dd);
  }
  element.append(list);
}

function stablePlanJson(plan) {
  return JSON.stringify(Object.fromEntries(Object.keys(plan || {}).sort().map(key => [key, plan[key]])));
}

async function renderPlanFingerprint(element, plan) {
  const source = stablePlanJson(plan);
  const token = String((Number(element.dataset.hashRequest || 0) + 1));
  element.dataset.hashRequest = token;
  element.textContent = 'Calculating';
  try {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(source));
    if (element.dataset.hashRequest !== token) return;
    element.textContent = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
  } catch {
    if (element.dataset.hashRequest === token) element.textContent = 'Unavailable in this browser';
  }
}

function selectedEvidenceOptions(plan) {
  const results = [];
  for (const settingId of ['run.surface', 'run.strategy', 'run.attack_script', 'runtime.emulator']) {
    const setting = findSetting(settingId);
    const option = optionOf(setting, plan[settingId]);
    if (option) results.push({ label: option.label, option });
  }
  const heroSetting = findSetting('run.heroes');
  for (const hero of asList(plan['run.heroes'])) {
    const option = optionOf(heroSetting, hero);
    if (option) results.push({ label: option.label, option });
  }
  for (const setting of allSettings()) {
    if (setting.availability && !same(plan[setting.id], setting.default)) {
      results.push({ label: setting.label, option: setting });
    }
  }
  return results;
}

function renderEvidence(element, plan, titleId = '') {
  element.replaceChildren();
  element.className = 'evidence-receipt';
  const evidence = selectedEvidenceOptions(plan);
  const blocked = evidence.filter(item => ['planned', 'unsupported'].includes(item.option.availability));
  const verified = evidence.filter(item => item.option.runtime_verified);
  const unverified = evidence.filter(item => !item.option.runtime_verified && !blocked.includes(item));
  const title = document.createElement('strong');
  if (titleId) title.id = titleId;
  const copy = document.createElement('p');
  if (blocked.length) {
    element.classList.add('blocked');
    title.textContent = 'Unavailable selections need attention';
    copy.textContent = `Unavailable: ${blocked.map(item => item.label).join(', ')}.`;
  } else if (unverified.length) {
    element.classList.add('review');
    title.textContent = 'Planned, issued, and confirmed are separate';
    const proven = verified.length ? `Confirmed route evidence: ${verified.map(item => item.label).join(', ')}. ` : '';
    copy.textContent = `${proven}Pending fresh confirmation: ${unverified.map(item => item.label).join(', ')}.`;
  } else {
    element.classList.add('verified');
    title.textContent = 'Selected routes have confirmed run evidence';
    copy.textContent = verified.map(item => item.label).join(', ');
  }
  element.append(title, copy);
}

function setStateLabel(element, text, kind = '') {
  element.textContent = text;
  element.className = `state-label ${kind}`.trim();
}

function renderPlanReceipts() {
  if (!META) return;
  const nativeCopy = NATIVE_PROFILE_MODE;
  $('runIntro').textContent = nativeCopy
    ? 'The active native profile, engine binding, and next safe action.'
    : 'The applied plan, engine binding, and next safe action.';
  $('routeModeKicker').textContent = nativeCopy ? 'Full profile automation' : 'Safe run route';
  $('routeOverviewTitle').textContent = nativeCopy
    ? 'Full profile. Launch the complete stack.'
    : 'Plan first. Prove every boundary.';
  $('routeOverviewCopy').textContent = nativeCopy
    ? 'Start uses the selected native profile through the current recognition and no-premium gates.'
    : 'Start advances only after the saved plan, managed engine, emulator identity, and village state pass their own checks.';
  $('routeStepOneTitle').textContent = nativeCopy ? 'Profile' : 'Plan';
  $('routeStepOneCopy').textContent = nativeCopy ? 'Use active native settings' : 'Apply exact work';
  $('routeStepOneMapLabel').textContent = nativeCopy ? '01 / PROFILE' : '01 / PLAN';
  $('routeMap').setAttribute('aria-label', nativeCopy
    ? 'A guarded route from the active native profile through the engine gate to the Home Village'
    : 'A guarded route from an applied plan through the engine gate to the Home Village');
  $('savedPlanTitle').textContent = nativeCopy ? 'Plan draft' : 'Saved plan';
  $('savedPlanFingerprintLabel').textContent = nativeCopy ? 'Draft fingerprint' : 'Saved plan fingerprint';
  $('savedPlanFingerprintHelp').textContent = nativeCopy
    ? 'SHA-256 of the visible draft values. Apply this draft to leave full profile automation.'
    : 'SHA-256 of the sorted saved values. Start uses this applied plan, never the visible draft.';
  renderMaintenanceRoutePreview();
  renderSummary($('planSummary'), PLAN);
  renderSummary($('savedPlanSummary'), SAVED);
  renderPlanFingerprint($('visiblePlanHash'), PLAN);
  renderPlanFingerprint($('savedPlanHash'), SAVED);
  renderEvidence($('banner'), PLAN, 'bannerText');
  renderEvidence($('runEvidence'), SAVED);
  $('runEvidence').hidden = nativeCopy;
  $('runValidation').hidden = nativeCopy;

  const visibleProblems = clientProblems(PLAN);
  const savedProblems = nativeCopy ? [] : clientProblems(SAVED);
  renderValidation($('validationList'), visibleProblems);
  renderValidation($('runValidationList'), savedProblems);

  const pending = allSettings().filter(isUnsaved).length;
  if (visibleProblems.length) setStateLabel($('visiblePlanState'), `${visibleProblems.length} issue${visibleProblems.length === 1 ? '' : 's'}`, 'error');
  else if (pending) setStateLabel($('visiblePlanState'), `${pending} unsaved`, 'warning');
  else setStateLabel($('visiblePlanState'), PLAN_WRITTEN ? 'Applied' : 'Not applied', PLAN_WRITTEN ? 'ready' : 'warning');

  if (nativeCopy) setStateLabel($('savedPlanState'), 'Native profile', 'ready');
  else if (savedProblems.length) setStateLabel($('savedPlanState'), `${savedProblems.length} issue${savedProblems.length === 1 ? '' : 's'}`, 'error');
  else if (!PLAN_WRITTEN) setStateLabel($('savedPlanState'), 'Not applied', 'warning');
  else if (pending) setStateLabel($('savedPlanState'), 'Applied; edits pending', 'warning');
  else setStateLabel($('savedPlanState'), 'Applied', 'ready');
}

function renderMaintenanceRoutePreview() {
  const preview = $('maintenanceRoutePreview');
  if (!preview) return;
  const visible = PLAN['run.strategy'] === 'home.collectors';
  preview.hidden = !visible;
  if (!visible) return;

  let selected = 0;
  let available = 0;
  let unavailable = 0;
  for (const item of MAINTENANCE_COLLECTIONS) {
    const enabled = PLAN[item.id] === true;
    const setting = findSetting(item.id);
    const locked = ['planned', 'unsupported'].includes(setting?.availability);
    const state = locked ? 'unavailable' : (enabled ? 'active' : 'off');
    if (locked) unavailable += 1;
    else available += 1;
    if (enabled && !locked) selected += 1;
    for (const node of preview.querySelectorAll(`[data-collection-key="${item.id}"]`)) {
      node.dataset.state = state;
      const status = node.querySelector('[data-route-status]');
      if (status) status.textContent = locked ? 'Unavailable' : (enabled ? 'Selected' : 'Available');
      if (node.matches('li')) node.setAttribute('aria-label', `${item.label}: ${locked ? 'unavailable' : (enabled ? 'selected' : 'available')}`);
    }
  }
  $('maintenanceRouteCount').textContent = `${selected} selected · ${available} available · ${unavailable} unavailable`;
}

function setSaveStatus(text, kind = '') {
  const status = $('status');
  status.className = `save-status ${kind}`.trim();
  status.textContent = text;
}

function updateDirty() {
  if (!META) return;
  const pending = allSettings().filter(isUnsaved).length;
  const changed = allSettings().filter(isChanged).length;
  const problems = clientProblems(PLAN);
  $('apply').disabled = !BOOT_READY || problems.length > 0 || (!pending && PLAN_WRITTEN);
  $('reset').disabled = !BOOT_READY;
  $('dirty').textContent = problems.length
    ? `${problems.length} issue${problems.length === 1 ? '' : 's'} block Apply`
    : pending
      ? `${pending} unsaved change${pending === 1 ? '' : 's'}`
      : !PLAN_WRITTEN
        ? 'Visible defaults have not been applied'
        : changed
          ? `${changed} setting${changed === 1 ? '' : 's'} differ from default`
          : 'Visible plan matches defaults';
  renderPlanReceipts();
  renderControl();
}

function readableState(state) {
  return ({
    offline: 'Engine offline',
    idle: 'Ready',
    starting: 'Starting',
    running: 'Run active',
    paused: 'Run paused',
    stopping: 'Stopping',
    closing: 'Closing',
    error: 'Status error',
  })[state] || String(state || 'Unknown');
}

function announceControl(text) {
  if (!text || text === LAST_CONTROL_ANNOUNCEMENT) return;
  LAST_CONTROL_ANNOUNCEMENT = text;
  $('controlAnnouncement').textContent = text;
}

function setControlNotice(text, kind = 'info', announce = true) {
  CONTROL_NOTICE = text;
  CONTROL_NOTICE_KIND = kind;
  if (announce) announceControl(text);
}

function setHealth(id, state, label) {
  const item = $(id);
  item.dataset.state = state;
  item.querySelector('strong').textContent = label;
}

function renderControl() {
  const connected = BOOT_READY && !!CONTROL.connected;
  const state = connected ? (CONTROL.state || 'idle') : 'offline';
  $('engineLamp').dataset.state = state;
  $('routeMap').dataset.state = state;
  $('engineState').textContent = readableState(state);
  $('engineMessage').textContent = CONTROL.message || (connected ? 'Native engine connected.' : 'Launch My Bot 2.0 to enable run controls.');
  const profileIdentity = connected ? (CONTROL.profile || 'Default') : 'Not connected';
  const emulatorIdentity = connected
    ? ([CONTROL.emulator, CONTROL.instance].filter(Boolean).join(' / ') || 'Not selected')
    : 'Not connected';
  const versionIdentity = connected && CONTROL.engine_version ? `Upstream ${CONTROL.engine_version}` : 'Not connected';
  for (const [id, identity] of [
    ['engineProfile', profileIdentity],
    ['engineEmulator', emulatorIdentity],
    ['engineVersion', versionIdentity],
  ]) {
    $(id).textContent = identity;
    $(id).title = identity;
  }

  setHealth('healthUi', BOOT_READY ? 'ready' : 'waiting', BOOT_READY ? 'Ready' : 'Loading');
  setHealth('healthNative', connected ? 'ready' : 'waiting', connected ? 'Connected' : 'Waiting');
  if (!connected) setHealth('healthEngine', 'waiting', 'Waiting');
  else if (CONTROL.engine_available === false) setHealth('healthEngine', 'error', 'Unavailable');
  else if (CONTROL.engine_probe_state === 'running') setHealth('healthEngine', 'warning', 'Checking');
  else if (CONTROL.engine_probe_state === 'passed') setHealth('healthEngine', 'ready', 'Ready');
  else setHealth('healthEngine', 'warning', 'Not checked');

  const emulator = [CONTROL.emulator, CONTROL.instance].filter(Boolean).join(' / ');
  const hasNativeWindowState = Object.prototype.hasOwnProperty.call(CONTROL, 'window_attached');
  const windowAttached = connected && (hasNativeWindowState ? CONTROL.window_attached === true : CONTROL.emulator_attached === true);
  const adbReady = windowAttached && CONTROL.adb_ready === true;
  const gameReady = adbReady && CONTROL.game_ready === true;
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
  const planLocked = connected && ['starting', 'running', 'paused', 'stopping'].includes(state);
  const savedProblems = META && !NATIVE_PROFILE_MODE ? clientProblems(SAVED) : [];
  const hasUnsavedPlan = !NATIVE_PROFILE_MODE
    && (!META || allSettings().some(isUnsaved) || !PLAN_WRITTEN || savedProblems.length > 0);
  const startCanBeStopped = ['start', 'check-engine', 'launch-game'].includes(CONTROL_PENDING?.action) && !!CONTROL_PENDING.request_id;
  const supervisedInitActive = CONTROL.engine_init_cancellable === true;
  const managedInitCanBeStopped = startCanBeStopped || supervisedInitActive;
  const engineAvailable = CONTROL.engine_available !== false;
  const recognitionAvailable = CONTROL.recognition_available === true;
  const nativeProfileBlocked = NATIVE_PROFILE_MODE && !recognitionAvailable;
  const recognitionError = CONTROL.recognition_error
    || 'Full profile automation requires licensed inherited recognition or a clean-room replacement.';
  $('controlStart').title = nativeProfileBlocked
    ? recognitionError
    : NATIVE_PROFILE_MODE
      ? 'Start the active native profile; BlueStacks and Clash of Clans will be launched if needed'
    : savedProblems.length
      ? 'Resolve and apply the saved plan issues before starting'
      : hasUnsavedPlan ? 'Apply the visible plan before starting' : 'Start the applied plan';
  $('controlStart').disabled = !BOOT_READY || busy || hasUnsavedPlan || !connected || !engineAvailable || nativeProfileBlocked || state !== 'idle';
  $('controlNativeMode').textContent = NATIVE_PROFILE_MODE ? 'Full profile automation active' : 'Use full profile automation';
  $('controlNativeMode').title = !recognitionAvailable
    ? recognitionError
    : NATIVE_PROFILE_MODE
      ? 'Apply a plan to return to a bounded planned route'
      : 'Back up the applied plan and run the saved native profile with its full configuration window and hard no-gem guard';
  $('controlNativeMode').disabled = !BOOT_READY || busy || !connected || state !== 'idle'
    || !recognitionAvailable || NATIVE_PROFILE_MODE;
  const nativeModeReason = $('controlNativeModeReason');
  if (!BOOT_READY) {
    nativeModeReason.textContent = 'Full profile availability is loading.';
    nativeModeReason.className = 'mode-availability';
  } else if (!connected) {
    nativeModeReason.textContent = 'Full profile automation requires a fresh native-engine heartbeat.';
    nativeModeReason.className = 'mode-availability warning';
  } else if (!recognitionAvailable) {
    nativeModeReason.textContent = recognitionError;
    nativeModeReason.className = 'mode-availability warning';
  } else {
    nativeModeReason.textContent = NATIVE_PROFILE_MODE
      ? 'The selected native profile is active; Apply a plan to return to a bounded route.'
      : 'Available: Start will use the selected native profile through current safety gates.';
    nativeModeReason.className = 'mode-availability ready';
  }
  let safeHomeReason = 'Load Home collection settings for review. Nothing is applied or started.';
  if (!BOOT_READY) safeHomeReason = 'Home-route preparation unlocks after the saved plan and engine state load.';
  else if (busy) safeHomeReason = 'Wait for the current native command to finish before changing the visible route.';
  else if (!connected) safeHomeReason = 'A fresh native-engine heartbeat is required before preparing a run.';
  else if (state !== 'idle') safeHomeReason = `Stop the current ${readableState(state).toLocaleLowerCase()} before preparing a Home route.`;
  $('controlSafeHomeRouteHelp').textContent = safeHomeReason;
  $('controlSafeHomeRoute').title = safeHomeReason;
  $('controlSafeHomeRoute').disabled = !BOOT_READY || busy || !connected || state !== 'idle';
  $('controlEngineCheck').disabled = !BOOT_READY || busy || !connected || !engineAvailable || state !== 'idle';
  $('controlEngineCheck').title = 'Initialize the managed engine without opening or controlling the emulator or game';
  $('controlGameLaunch').disabled = !BOOT_READY || busy || !connected || state !== 'idle';
  $('controlGameLaunch').title = 'Start the exact BlueStacks 5 instance and Clash of Clans, passively prove Home, then return idle';
  $('controlPause').disabled = !BOOT_READY || busy || !connected || !['running', 'paused'].includes(state);
  $('controlStop').disabled = !BOOT_READY || (!connected && !managedInitCanBeStopped) || (busy && !managedInitCanBeStopped)
    || (!managedInitCanBeStopped && !['starting', 'running', 'paused'].includes(state));
  $('controlPause').textContent = state === 'paused' ? 'Resume' : 'Pause';
  if (planLocked) {
    $('apply').disabled = true;
    $('apply').title = 'The applied plan is immutable while a run is active';
  } else {
    const visibleProblems = META ? clientProblems(PLAN) : [];
    const pendingEdits = META ? allSettings().some(isUnsaved) : false;
    $('apply').disabled = !BOOT_READY || visibleProblems.length > 0 || (!pendingEdits && PLAN_WRITTEN);
    $('apply').title = 'Apply the visible plan to disk';
  }

  if (!BOOT_READY) {
    $('controlAck').textContent = 'Controls unlock after the saved plan and engine state load.';
    $('controlAck').className = 'control-ack';
  } else if (CONTROL_PENDING) {
    const phase = CONTROL_PENDING.accepted_at ? 'accepted; waiting for completion' : 'queued; waiting for native acknowledgement';
    const cancellation = startCanBeStopped ? ' Stop remains available.' : '';
    $('controlAck').textContent = `${CONTROL_PENDING.action} command ${phase}.${cancellation}`;
    $('controlAck').className = 'control-ack pending';
  } else if (CONTROL_NOTICE) {
    $('controlAck').textContent = CONTROL_NOTICE;
    $('controlAck').className = `control-ack notice ${CONTROL_NOTICE_KIND}`;
  } else if (supervisedInitActive) {
    $('controlAck').textContent = 'Managed engine initialization is active. Stop remains available through launcher supervision.';
    $('controlAck').className = 'control-ack pending';
  } else if (nativeProfileBlocked && connected) {
    $('controlAck').textContent = `${recognitionError} Apply a verified bounded route to run safely.`;
    $('controlAck').className = 'control-ack notice warning';
  } else if (NATIVE_PROFILE_MODE && connected) {
    $('controlAck').textContent = 'Full profile automation is active. Start uses the selected native profile through current recognition and no-premium gates, and launches BlueStacks and Clash of Clans if needed.';
    $('controlAck').className = 'control-ack';
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
    if (CONTROL.engine_init_cancellable === true) {
      CONTROL_OFFLINE_SINCE = null;
      return;
    }
    if (CONTROL_OFFLINE_SINCE == null) CONTROL_OFFLINE_SINCE = now;
    if (now - CONTROL_OFFLINE_SINCE >= CONTROL_OFFLINE_GRACE_MS) {
      setControlNotice(`${CONTROL_PENDING.action} tracking stopped because the native engine went offline before a final outcome.`, 'error');
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
    setControlNotice(`${CONTROL_PENDING.action} tracking stopped after no ${wait} arrived within ${Math.round(timeout / 1000)} seconds.`, 'error');
    CONTROL_PENDING = null;
  }
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.message || payload.problems?.join('; ') || `${url} returned ${response.status}`);
  return payload;
}

async function pollControl() {
  if (hiddenIdlePollingSuspended()) {
    CONTROL_TIMER = null;
    return;
  }
  const previousInstanceSignature = LAST_INSTANCE_SIGNATURE;
  try {
    CONTROL = await fetchJson('/api/control/status', { cache: 'no-store' });
    LAST_INSTANCE_SIGNATURE = [CONTROL.connected, CONTROL.emulator, CONTROL.instance].join('|');
    if (CONTROL_PENDING && CONTROL_PENDING.request_id
        && CONTROL.last_command_id === CONTROL_PENDING.request_id
        && CONTROL.last_command === CONTROL_PENDING.action) {
      const outcome = CONTROL.last_outcome || '';
      if (outcome === 'accepted') {
        if (!CONTROL_PENDING.accepted_at) {
          CONTROL_PENDING.accepted_at = Date.now();
          announceControl(`${CONTROL_PENDING.action} command accepted by the native engine.`);
        }
      } else if (outcome === 'started' && CONTROL_PENDING.action === 'start') {
        CONTROL_STARTED = { request_id: CONTROL_PENDING.request_id };
        setControlNotice(`started: ${CONTROL.last_command_message || CONTROL.message || 'Run started'}`, 'info');
        CONTROL_PENDING = null;
      } else if (CONTROL_TERMINAL_OUTCOMES.has(outcome)) {
        setControlNotice(`${outcome}: ${CONTROL.last_command_message || CONTROL.message || `${CONTROL_PENDING.action} command processed`}`,
          ['rejected', 'failed'].includes(outcome) ? 'error' : 'info');
        CONTROL_PENDING = null;
      }
    }
    if (!CONTROL_PENDING && CONTROL_STARTED
        && CONTROL.last_command_id === CONTROL_STARTED.request_id
        && CONTROL.last_command === 'start'
        && CONTROL_TERMINAL_OUTCOMES.has(CONTROL.last_outcome || '')) {
      const outcome = CONTROL.last_outcome;
      setControlNotice(`${outcome}: ${CONTROL.last_command_message || CONTROL.message || 'Run completed'}`,
        ['rejected', 'failed'].includes(outcome) ? 'error' : 'info');
      CONTROL_STARTED = null;
    }
  } catch {
    CONTROL = { connected: false, state: 'offline', message: 'Control service is unreachable.' };
  }
  recoverControlPending();
  renderControl();
  if (META && LAST_INSTANCE_SIGNATURE !== previousInstanceSignature) refreshInstanceControl();
  const delay = controlPollDelay();
  CONTROL_TIMER = delay == null ? null : setTimeout(pollControl, delay);
}

function controlActivityIsActive() {
  return !!CONTROL_PENDING || ['starting', 'running', 'stopping'].includes(CONTROL.state);
}

function hiddenIdlePollingSuspended() {
  return document.hidden && !controlActivityIsActive();
}

function controlPollDelay() {
  if (controlActivityIsActive()) return document.hidden ? 1500 : 500;
  return document.hidden ? null : 5000;
}

function refreshInstanceControl() {
  const oldControl = $('f_runtime.instance');
  if (!oldControl || document.activeElement === oldControl) return;
  const setting = findSetting('runtime.instance');
  const field = oldControl.closest('.field');
  const replacement = makeControl(setting);
  replacement.id = oldControl.id;
  replacement.disabled = oldControl.disabled;
  replacement.required = oldControl.required;
  replacement.setAttribute('aria-describedby', oldControl.getAttribute('aria-describedby') || '');
  replacement.onchange = () => {
    PLAN[setting.id] = readControl(setting, replacement);
    markPresetCustom(setting.id);
    refreshAfterChange(setting, replacement.id);
  };
  field?.replaceChild(replacement, oldControl);
}

async function sendControl(action) {
  if (!BOOT_READY) return;
  if (action !== 'start') CONTROL_STARTED = null;
  const previousPending = CONTROL_PENDING;
  const replacingStart = action === 'stop' && ['start', 'check-engine', 'launch-game'].includes(previousPending?.action) && !!previousPending.request_id;
  if (CONTROL_PENDING && !replacingStart) return;
  if (action === 'start' && !NATIVE_PROFILE_MODE
      && (allSettings().some(isUnsaved) || !PLAN_WRITTEN || clientProblems(SAVED).length)) {
    setControlNotice('Apply the visible plan before Start. No unsaved value was sent to the engine.', 'warning');
    renderControl();
    return;
  }
  setControlNotice('', 'info', false);
  CONTROL_PENDING = { action, request_id: null, queued_at: Date.now(), accepted_at: null };
  renderControl();
  try {
    const response = await fetch('/api/control/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action,
        ...(replacingStart ? { expected_start_request_id: previousPending.request_id } : {}),
      }),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      setControlNotice((payload.problems || ['Command was refused.']).join('; '), 'error');
      CONTROL_PENDING = replacingStart ? previousPending : null;
    } else {
      CONTROL_PENDING = { action, request_id: payload.request_id, queued_at: Date.now(), accepted_at: null };
      announceControl(`${action} command queued for the native engine.`);
    }
  } catch {
    setControlNotice('Could not reach the local control service.', 'error');
    CONTROL_PENDING = replacingStart ? previousPending : null;
  }
  renderControl();
  clearTimeout(CONTROL_TIMER);
  CONTROL_TIMER = setTimeout(pollControl, 0);
  clearTimeout(EVENTS_TIMER);
  EVENTS_TIMER = setTimeout(pollEvents, 0);
}

async function activateNativeProfileMode() {
  if (!BOOT_READY || CONTROL_PENDING || NATIVE_PROFILE_MODE) return;
  const button = $('controlNativeMode');
  button.disabled = true;
  try {
    const response = await fetch('/api/plan/native', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      setControlNotice((payload.problems || ['Full profile automation was refused.']).join('; '), 'error');
      return;
    }
    NATIVE_PROFILE_MODE = true;
    PLAN_WRITTEN = false;
    const backup = payload.backup ? ` The applied plan was backed up to ${payload.backup}.` : '';
    setControlNotice(`Full profile automation is active.${backup} Start will use the selected native profile through current recognition and no-premium gates.`, 'info');
    setSaveStatus('Full profile automation is active. Apply the visible plan to return to a bounded planned route.', 'warn');
    updateDirty();
  } catch {
    setControlNotice('Could not reach the planner service. The applied plan was left unchanged.', 'error');
  } finally {
    renderControl();
  }
}

function prepareVerifiedHomeRoute() {
  if (!BOOT_READY) return;
  if (CONTROL_PENDING) {
    setControlNotice('Wait for the current native command to finish before changing the visible route.', 'warning');
    renderControl();
    return;
  }
  if (!CONTROL.connected || CONTROL.state !== 'idle') {
    setControlNotice('A fresh connected idle native engine is required before preparing a Home route.', 'warning');
    renderControl();
    return;
  }
  if (!applyStrategySafetyPatch('home.collectors')) {
    setControlNotice('The bounded Home route could not be loaded.', 'error');
    return;
  }
  setView('plan', { updateHash: true, focusHeading: true });
  setGroup('between', { updateHash: true, focusGroup: true });
  setControlNotice('Collectors-only safety settings are visible for review. Apply plan, then Start remains a separate action.', 'info');
  renderControl();
}

$('controlStart').onclick = () => sendControl('start');
$('controlEngineCheck').onclick = () => sendControl('check-engine');
$('controlGameLaunch').onclick = () => sendControl('launch-game');
$('controlPause').onclick = () => sendControl(CONTROL.state === 'paused' ? 'resume' : 'pause');
$('controlStop').onclick = () => sendControl('stop');
$('controlNativeMode').onclick = activateNativeProfileMode;
$('controlSafeHomeRoute').onclick = prepareVerifiedHomeRoute;

function capabilityLabel(id) {
  const labels = {
    'battle.regular-ranked-split': 'Regular and Ranked battle routing',
    'battle.revenge': 'Revenge battles',
    'battle.legend-tiers': 'Legend League tiers',
    'battle.fast-forward': 'Battle speed-up',
    'army.training': 'Army training',
    'army.recipes': 'Army recipes',
    'army.cookbook': 'Army Cookbook',
    'heroes.six-slot-layout': 'Six-Hero roster and four active slots',
    'heroes.dragon-duke': 'Dragon Duke',
    'heroes.hero-journey': 'Hero Journey',
    'village.collectors': 'Collectors and mines',
    'village.donations': 'Donate and request',
    'village.upgrades-home': 'Home Village upgrades',
    'village.laboratory': 'Laboratory research',
    'village.town-hall-18': 'Town Hall 18 recognition',
    'village.guardians': 'Guardians',
    'builder-base.upgrades': 'Builder Base upgrades',
    'builder-base.battles': 'Builder Base battles',
    'builder-base.additional-builder': 'Additional Builder',
    'clan-capital.upgrades': 'Clan Capital upgrades',
    'events.clan-games': 'Clan Games',
    'orchestration.multi-account': 'Multi-account rotation',
    'orchestration.account-queue': 'Account queue',
    'runtime.recovery': 'Interruption and restart recovery',
    'chat.global-chat': 'Global Chat handling',
  };
  if (labels[id]) return labels[id];
  return String(id || 'unknown capability')
    .split('.')
    .flatMap(part => part.split('-'))
    .filter(Boolean)
    .map(word => word[0].toLocaleUpperCase() + word.slice(1))
    .join(' ');
}

function capabilityPublicState(status) {
  if (status === 'supported') return 'Supported';
  if (status === 'legacy-implemented') return 'Inherited';
  if (['adapter-added', 'engine-added'].includes(status)) return 'Implemented';
  if (status === 'fixture-required') return 'Fixture required';
  return 'Unavailable';
}

function capabilityGroupsForCatalog(capabilities) {
  const catalogIds = capabilities.map(capability => capability.id).filter(Boolean);
  const assigned = new Set(CAPABILITY_GROUPS.flatMap(group => group.ids));
  const additional = catalogIds.filter(id => !assigned.has(id)).sort((left, right) => left.localeCompare(right));
  return additional.length
    ? [...CAPABILITY_GROUPS, { label: 'Additional inventoried scope', ids: additional }]
    : CAPABILITY_GROUPS;
}

function renderEvidenceReadiness(summary) {
  const total = Number(summary?.capabilities);
  const historical = Number(summary?.historical_ready_for_review);
  const exactCurrent = Number(summary?.exact_current_ready_for_review);
  const exactRecords = Number(summary?.exact_current_evidence_records);
  const fixtures = summary?.fixture_inventory || {};
  const fixtureTotal = Number(fixtures.total);
  const fixtureVerified = Number(fixtures.verified);
  const fixtureComplete = Number(fixtures.complete);
  const fixtureMissing = Number(fixtures.missing);
  const countsValid = summary?.valid === true
    && [total, historical, exactCurrent, exactRecords, fixtureTotal, fixtureVerified, fixtureComplete, fixtureMissing]
      .every(value => Number.isInteger(value) && value >= 0);
  if (!countsValid) {
    $('evidenceHistoricalReady').textContent = 'Unavailable';
    $('evidenceExactCurrentReady').textContent = 'Unavailable';
    $('evidenceVerifiedFixtures').textContent = 'Unavailable';
    $('evidenceReadinessNote').textContent = 'The local evidence evaluator failed closed. No readiness is inferred.';
    return;
  }
  $('evidenceHistoricalReady').textContent = `${historical} / ${total}`;
  $('evidenceExactCurrentReady').textContent = `${exactCurrent} / ${total}`;
  $('evidenceVerifiedFixtures').textContent = `${fixtureVerified} / ${fixtureTotal}`;
  $('evidenceHistoricalReady').setAttribute('aria-label', `${historical} of ${total} capabilities have historical review readiness`);
  $('evidenceExactCurrentReady').setAttribute('aria-label', `${exactCurrent} of ${total} capabilities have exact-current binary proof`);
  $('evidenceVerifiedFixtures').setAttribute('aria-label', `${fixtureVerified} of ${fixtureTotal} fixture records are verified`);
  $('evidenceReadinessNote').textContent = `${exactRecords} exact-current evidence records. ${fixtureComplete} captures complete; ${fixtureMissing} still missing. Historical proof never promotes current support by itself.`;
}

function renderCapabilityOverview(capabilities) {
  const surfaced = capabilities.filter(capability => capability?.id);
  const counts = { Supported: 0, Implemented: 0, Inherited: 0, Gated: 0 };
  for (const capability of surfaced) {
    const state = capabilityPublicState(capability.status);
    if (Object.prototype.hasOwnProperty.call(counts, state)) counts[state] += 1;
    else counts.Gated += 1;
  }
  const total = surfaced.length;
  $('capabilityCountSupported').textContent = counts.Supported;
  $('capabilityCountImplemented').textContent = counts.Implemented;
  $('capabilityCountInherited').textContent = counts.Inherited;
  $('capabilityCountGated').textContent = counts.Gated;
  $('capabilityGraphicTotal').textContent = total;
  $('capabilityGraphicSupported').textContent = `${counts.Supported} SUPPORTED`;
  $('capabilityGraphicImplemented').textContent = `${counts.Implemented} IMPLEMENTED`;
  $('capabilityGraphicInherited').textContent = `${counts.Inherited} INHERITED`;
  $('capabilityGraphicGated').textContent = `${counts.Gated} GATED`;
  $('capabilityOverviewSummary').textContent = total
    ? `${total} capabilities are surfaced here. ${counts.Supported} are declared supported; the release evidence gate is reported separately below.`
    : 'No surfaced capability states were returned. Nothing is treated as supported.';
  for (const [state, count] of Object.entries(counts)) {
    $(`capabilitySignal${state}`).dataset.active = String(count > 0);
  }
  renderEvidenceReadiness(EVIDENCE_READINESS);
}

function renderCapabilities() {
  const root = $('capabilityList');
  root.replaceChildren();
  const capabilities = CAPABILITY_CATALOG.capabilities || [];
  const byId = new Map(capabilities.map(item => [item.id, item]));
  const groups = capabilityGroupsForCatalog(capabilities);
  renderCapabilityOverview(capabilities);
  for (const group of groups) {
    const section = document.createElement('section');
    section.className = 'capability-group';
    const heading = document.createElement('h4');
    heading.textContent = group.label;
    section.append(heading);
    for (const id of group.ids) {
      const capability = byId.get(id);
      if (!capability) continue;
      const row = document.createElement('div');
      row.className = 'capability-row';
      row.dataset.capabilityId = id;
      const name = document.createElement('strong');
      name.textContent = capabilityLabel(id);
      const state = document.createElement('span');
      state.className = `capability-state status-${capability.status}`;
      state.textContent = capabilityPublicState(capability.status);
      const reason = document.createElement('p');
      reason.className = 'sr-only';
      reason.textContent = CAPABILITY_CATALOG.status_definitions?.[capability.status]
        || 'No reviewed current-client proof statement is available.';
      state.setAttribute('aria-label', `${state.textContent}. ${reason.textContent}`);
      row.append(name, state, reason);
      section.append(row);
    }
    root.append(section);
  }
  if (!root.children.length) {
    const empty = document.createElement('p');
    empty.className = 'empty-state';
    empty.textContent = 'The capability catalog did not load.';
    root.append(empty);
  }
}

function eventDate(event) {
  const candidate = event.timestamp ?? event.at;
  if (candidate == null) return null;
  const date = new Date(candidate);
  return Number.isNaN(date.getTime()) ? null : date;
}

function elapsedEventTime(event) {
  const elapsed = Number(event.timestamp_ms);
  if (!Number.isFinite(elapsed) || elapsed < 0) return '';
  if (elapsed < 1000) return `+${Math.round(elapsed)}ms`;
  return `+${(elapsed / 1000).toFixed(elapsed % 1000 === 0 ? 0 : 3)}s`;
}

function humanizeEventType(type) {
  return String(type || 'event').replace(/[._-]+/g, ' ').replace(/^\w/, letter => letter.toUpperCase());
}

function renderActivityList(element, limit) {
  element.replaceChildren();
  if (EVENTS_ERROR) {
    const item = document.createElement('li');
    item.className = 'empty-state';
    item.textContent = 'Activity is unavailable; the local event service did not respond.';
    element.append(item);
    return;
  }
  const events = EVENTS.slice(-limit).reverse();
  if (!events.length) {
    const item = document.createElement('li');
    item.className = 'empty-state';
    item.textContent = 'No events have been recorded for this run.';
    element.append(item);
    return;
  }
  for (const event of events) {
    const item = document.createElement('li');
    item.className = 'activity-item';
    const severityValue = ['error', 'warning', 'info', 'debug'].includes(event.severity) ? event.severity : 'info';
    const severity = document.createElement('span');
    severity.className = `activity-severity ${severityValue}`;
    severity.textContent = severityValue;
    const message = document.createElement('span');
    message.className = 'activity-message';
    const type = document.createElement('strong');
    type.textContent = humanizeEventType(event.type);
    message.append(type, document.createTextNode(event.message ? ` ${event.message}` : ''));
    const time = document.createElement('time');
    const date = eventDate(event);
    if (date) {
      time.dateTime = date.toISOString();
      time.textContent = date.toLocaleString([], { dateStyle: 'short', timeStyle: 'medium' });
    } else {
      const elapsed = Number(event.timestamp_ms);
      time.textContent = elapsedEventTime(event) || 'Time not recorded';
      if (Number.isFinite(elapsed) && elapsed >= 0) time.dateTime = `PT${elapsed / 1000}S`;
    }
    item.append(severity, message, time);
    element.append(item);
  }
}

function renderActivity() {
  renderActivityList($('recentEvents'), 5);
  renderActivityList($('events'), 20);
}

async function pollEvents() {
  if (hiddenIdlePollingSuspended()) {
    EVENTS_TIMER = null;
    return;
  }
  try {
    const payload = await fetchJson('/api/events', { cache: 'no-store' });
    EVENTS = Array.isArray(payload.events) ? payload.events : [];
    EVENTS_ERROR = '';
  } catch {
    EVENTS_ERROR = 'unavailable';
  }
  renderActivity();
  const delay = eventPollDelay();
  EVENTS_TIMER = delay == null ? null : setTimeout(pollEvents, delay);
}

function eventPollDelay() {
  if (controlActivityIsActive()) return document.hidden ? 5000 : 1500;
  return document.hidden ? null : 15000;
}

async function loadNativeLog({ automatic = false } = {}) {
  const status = $('nativeLogStatus');
  const output = $('nativeLogText');
  if (automatic && document.activeElement === output) {
    status.textContent = 'Automatic refresh is paused while the raw log has keyboard focus.';
    return;
  }
  $('refreshNativeLog').disabled = true;
  status.textContent = automatic ? 'Refreshing the bounded log tail.' : 'Loading the active profile log.';
  try {
    const payload = await fetchJson('/api/log', { cache: 'no-store' });
    const wasNearEnd = output.scrollHeight - output.scrollTop - output.clientHeight < 28;
    output.textContent = payload.available ? (payload.text || 'The native log is empty.') : payload.message;
    if (wasNearEnd) output.scrollTop = output.scrollHeight;
    status.textContent = payload.available
      ? `${payload.path} · ${Number(payload.size_bytes || 0).toLocaleString()} bytes${payload.truncated ? ' · bounded tail' : ''}`
      : payload.message;
    $('downloadNativeLog').hidden = !payload.available;
  } catch {
    output.textContent = 'The raw log could not be loaded.';
    status.textContent = 'The local log service is unavailable.';
    $('downloadNativeLog').hidden = true;
  } finally {
    $('refreshNativeLog').disabled = false;
  }
}

function scheduleNativeLogRefresh() {
  clearTimeout(LOG_REFRESH_TIMER);
  if (!$('rawLogDetails').open || !$('followNativeLog').checked) return;
  LOG_REFRESH_TIMER = setTimeout(async () => {
    await loadNativeLog({ automatic: true });
    scheduleNativeLogRefresh();
  }, 2500);
}

$('rawLogDetails').addEventListener('toggle', async () => {
  if ($('rawLogDetails').open) {
    await loadNativeLog();
    scheduleNativeLogRefresh();
  } else {
    clearTimeout(LOG_REFRESH_TIMER);
    LOG_REFRESH_TIMER = null;
  }
});
$('refreshNativeLog').onclick = async () => {
  await loadNativeLog();
  scheduleNativeLogRefresh();
};
$('followNativeLog').onchange = scheduleNativeLogRefresh;

async function savePlan() {
  if (!BOOT_READY || clientProblems(PLAN).length) return false;
  if (CONTROL.connected && ['starting', 'running', 'paused', 'stopping'].includes(CONTROL.state)) {
    setSaveStatus('The applied plan is locked until the active run stops.', 'bad');
    return false;
  }
  const button = $('apply');
  button.disabled = true;
  setSaveStatus('Applying the visible plan.', 'warn');
  try {
    const response = await fetch('/api/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(PLAN),
    });
    const payload = await response.json();
    if (!response.ok || !payload.ok) {
      setSaveStatus((payload.problems || ['The plan was refused.']).join('; '), 'bad');
      updateDirty();
      return false;
    }
    PLAN = payload.plan;
    SAVED = clone(PLAN);
    PLAN_WRITTEN = true;
    NATIVE_PROFILE_MODE = false;
    const matched = matchingPresetForPlan();
    SELECTED_PRESET = matched?.id || 'custom';
    $('presetSelect').value = SELECTED_PRESET;
    drawPlanPanel();
    updatePlanGroupNav();
    renderPresetPreview();
    updateDirty();
    const heroes = selectedHeroLabels();
    const problems = payload.problems || [];
    setSaveStatus(problems.length
      ? problems.join('; ')
      : `Applied to ${payload.written}. Heroes: ${heroes.length ? heroes.join(', ') : 'none'}.`,
    problems.length ? 'warn' : 'ok');
    announceControl('Plan applied. Start remains a separate action in Run.');
    return true;
  } catch {
    setSaveStatus('Could not reach the planner service. No plan receipt was returned.', 'bad');
    updateDirty();
    return false;
  }
}

$('apply').onclick = savePlan;
$('reset').onclick = () => {
  if (!BOOT_READY) return;
  for (const setting of allSettings()) PLAN[setting.id] = clone(defaultFor(setting));
  markPresetCustom();
  drawPlanPanel();
  updatePlanGroupNav();
  renderPresetPreview();
  updateDirty();
  setSaveStatus('Visible plan reset to defaults. Apply is still required.', 'warn');
};

$('filter').oninput = event => {
  FILTER = event.target.value.trim().toLocaleLowerCase();
  drawPlanPanel();
  updatePlanGroupNav();
};

$('exportDiagnostics').onclick = async () => {
  if (!BOOT_READY) return;
  const button = $('exportDiagnostics');
  button.disabled = true;
  const original = button.textContent;
  button.textContent = 'Preparing';
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
    setControlNotice('Diagnostic bundle exported. It contains allowlisted operational state only.');
  } catch {
    setControlNotice('Diagnostic export failed. The local service may be unavailable.', 'error');
  } finally {
    button.disabled = false;
    button.textContent = original;
    renderControl();
  }
};

function setBootControls(enabled) {
  for (const button of viewButtons) button.disabled = !enabled;
  $('editPlan').disabled = !enabled;
  $('openDiagnostics').disabled = !enabled;
  $('filter').disabled = !enabled;
  $('presetSelect').disabled = !enabled;
  $('reset').disabled = !enabled;
  $('exportDiagnostics').disabled = !enabled;
  $('refreshNativeLog').disabled = !enabled;
  $('followNativeLog').disabled = !enabled;
  if (!enabled) $('controlNativeMode').disabled = true;
  if (!enabled) $('controlSafeHomeRoute').disabled = true;
  if (!enabled) $('apply').disabled = true;
}

function enforceNativeFixedValues(plan) {
  for (const setting of allSettings()) {
    if (Object.prototype.hasOwnProperty.call(setting, 'native_fixed_value')) {
      plan[setting.id] = clone(setting.native_fixed_value);
    }
  }
}

function stopPolls() {
  clearTimeout(CONTROL_TIMER);
  clearTimeout(EVENTS_TIMER);
  CONTROL_TIMER = null;
  EVENTS_TIMER = null;
}

function startPolls() {
  stopPolls();
  if (hiddenIdlePollingSuspended()) return;
  pollControl();
  pollEvents();
}

function showBootFailure(error) {
  BOOT_READY = false;
  document.body.classList.add('is-booting');
  $('workspace').hidden = true;
  $('bootShell').hidden = false;
  $('bootTitle').textContent = 'The control center did not load';
  $('bootStatus').textContent = `${error.message || 'The local planner service did not return a complete response.'} No plan or command was sent.`;
  $('bootRetry').hidden = false;
  setBootControls(false);
  CONTROL = { connected: false, state: 'offline', message: 'Control center load failed.' };
  renderControl();
}

async function boot() {
  BOOT_READY = false;
  stopPolls();
  setBootControls(false);
  $('bootRetry').hidden = true;
  $('bootTitle').textContent = 'Loading the control center';
  $('bootStatus').textContent = 'Reading metadata, the saved plan, and the native heartbeat.';
  $('bootShell').hidden = false;
  $('workspace').hidden = true;
  document.body.classList.add('is-booting');
  renderControl();
  try {
    const [metadataPayload, plan, health] = await Promise.all([
      fetchJson('/api/metadata', { cache: 'no-store' }),
      fetchJson('/api/plan', { cache: 'no-store' }),
      fetchJson('/api/health', { cache: 'no-store' }),
    ]);
    if (!metadataPayload.metadata || !Array.isArray(metadataPayload.metadata.sections)) {
      throw new Error('Planner metadata was incomplete.');
    }
    META = metadataPayload.metadata;
    CAPABILITY_CATALOG = metadataPayload.capabilities || CAPABILITY_CATALOG;
    EVIDENCE_READINESS = metadataPayload.evidence_readiness || null;
    PLAN = plan;
    SAVED = clone(plan);
    enforceNativeFixedValues(PLAN);
    CONTROL = health.engine || CONTROL;
    LAST_INSTANCE_SIGNATURE = [CONTROL.connected, CONTROL.emulator, CONTROL.instance].join('|');
    PLAN_WRITTEN = health.plan?.state === 'saved';
    NATIVE_PROFILE_MODE = health.plan?.mode === 'native-profile';
    FILTER = '';
    $('filter').value = '';
    initializePresets();
    initializePlanGroupNav();
    drawPlanPanel();
    renderCapabilities();
    EVENTS = [];
    EVENTS_ERROR = '';
    renderActivity();
    BOOT_READY = true;
    setBootControls(true);
    document.body.classList.remove('is-booting');
    $('bootShell').hidden = true;
    $('workspace').hidden = false;
    applyLocation();
    renderPresetPreview();
    updateDirty();
    renderControl();
    startPolls();
  } catch (error) {
    showBootFailure(error);
  }
}

$('bootRetry').onclick = boot;
document.addEventListener('visibilitychange', () => {
  if (!BOOT_READY) return;
  if (hiddenIdlePollingSuspended()) stopPolls();
  else startPolls();
});
boot();
