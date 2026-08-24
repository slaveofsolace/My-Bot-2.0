import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
HTML = (ROOT / "ui" / "planner.html").read_text(encoding="utf-8")
JS = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")
CSS = (ROOT / "ui" / "planner.css").read_text(encoding="utf-8")
METADATA = json.loads((ROOT / "config" / "ui" / "run-planner.settings.json").read_text(encoding="utf-8"))


class PlannerWorkbenchContract(unittest.TestCase):
    def test_nine_operator_surfaces_and_five_physical_panels_are_stable(self):
        self.assertEqual(
            re.findall(r'data-view="([^"]+)"', HTML),
            ["overview", "planner", "farming", "builder", "upgrades", "accounts", "activity", "settings", "about"],
        )
        self.assertIn("const VIEW_IDS = ['run', 'plan', 'village', 'activity', 'diagnostics'];", JS)
        self.assertIn("const SURFACE_DEFINITIONS = [", JS)
        for surface in ("overview", "planner", "farming", "builder", "upgrades", "accounts", "activity", "settings", "about"):
            self.assertIn(f"id: '{surface}'", JS)
        for legacy, current in (("run", "overview"), ("plan", "planner"), ("diagnostics", "about")):
            self.assertIn(f"{legacy}: '{current}'", JS)
        self.assertIn("renderCapabilities();", JS)
        prefix = JS.split("const $ =", 1)[0]
        plan_groups = JS.split("const PLAN_GROUPS = [", 1)[1].split("];", 1)[0]
        self.assertEqual(re.findall(r"id: '([^']+)'", plan_groups), ["match", "runtime", "targets", "between", "advanced"])

        grouped = [
            section_id
            for declaration in re.findall(r"sections:\s*\[([^]]*)\]", prefix)
            for section_id in re.findall(r"'([^']+)'", declaration)
        ]
        metadata_sections = [section["id"] for section in METADATA["sections"]]
        self.assertCountEqual(grouped, metadata_sections)
        self.assertEqual(len(grouped), len(set(grouped)))

    def test_all_settings_survive_and_free_text_types_are_explicit(self):
        settings = {setting["id"]: setting for section in METADATA["sections"] for setting in section["settings"]}
        self.assertEqual(len(settings), 48)
        treasury = settings["events.collect_treasury"]
        self.assertEqual(treasury["type"], "boolean")
        self.assertFalse(treasury["default"])
        loot_cart = settings["events.collect_loot_cart"]
        self.assertEqual(loot_cart["type"], "boolean")
        self.assertFalse(loot_cart["default"])
        self.assertEqual(loot_cart["engine_binding"], "RunPlan.events_collect_loot_cart")
        self.assertEqual(loot_cart["availability"], "gated")
        self.assertEqual(treasury["availability"], "planned")
        self.assertEqual(settings["events.collect_daily_reward"]["default"], False)
        self.assertEqual(settings["events.collect_daily_reward"]["type"], "boolean")
        self.assertEqual(settings["events.collect_daily_reward"]["availability"], "gated")
        self.assertEqual(settings["run.town_hall"]["default"], 0)
        self.assertEqual(settings["runtime.instance"]["type"], "instance-select")
        self.assertEqual(settings["army.recipe_name"]["type"], "text")
        self.assertEqual(settings["run.diagnostic_note"]["type"], "text")
        self.assertIn("control.type = 'text'", JS)

    def test_home_maintenance_route_has_a_truthful_visual_preview(self):
        for token in (
            'id="maintenanceRoutePreview"',
            'id="maintenanceRouteCount" aria-live="polite"',
            'data-collection-key="events.collect_resources"',
            'data-collection-key="events.collect_loot_cart"',
            'data-collection-key="events.collect_treasury"',
            'data-collection-key="events.collect_daily_reward"',
            "Battles, training, donations, upgrades, and gem conversion stay outside this route.",
        ):
            self.assertIn(token, HTML)
        self.assertIn("function renderMaintenanceRoutePreview()", JS)
        self.assertIn("PLAN['run.strategy'] === 'home.collectors'", JS)
        self.assertIn("renderMaintenanceRoutePreview();", JS)
        self.assertIn("const state = locked ? 'unavailable' : (enabled ? 'active' : 'off');", JS)
        self.assertIn("${selected} selected · ${available} available", JS)
        self.assertIn('.maintenance-node[data-state="unavailable"]', CSS)
        self.assertIn('@media (prefers-reduced-motion: reduce)', CSS)
        self.assertIn("setting.id === 'events.collect_loot_cart') PLAN['events.collect_resources'] = false;", JS)
        self.assertEqual(len(set(re.findall(r'<g class="maintenance-node"[^>]+transform="([^"]+)"', HTML))), 4)

    def test_run_view_has_a_distinct_no_gems_route_and_exact_recovery_language(self):
        for token in (
            '<span class="beacon-eyebrow">Run state</span>',
            'class="safety-rail" aria-label="Run safety contract"',
            'class="route-readiness" aria-label="Current run readiness"',
            "Operational overview",
            "Hard stop on gem surfaces",
            "Profile and emulator bound",
            "Issued is not confirmed",
            'class="route-gate-ring route-gate-ring-a"',
            "Recovery stays exact.",
            "Only receipt-bound launcher, controller, backend, and planner processes may be closed.",
        ):
            self.assertIn(token, HTML)
        self.assertIn(".engine-summary:has(.status-lamp[data-state=\"error\"])", CSS)
        self.assertIn(".safety-rail {", CSS)
        self.assertIn(".route-readiness {", CSS)
        self.assertIn("$('routeMap').dataset.state = state;", JS)
        self.assertIn("'.route-readiness-next', nextAction", JS)
        self.assertIn('.route-map:is([data-state="starting"], [data-state="running"]) .route-signal', CSS)
        self.assertNotIn("route-radar", CSS)
        self.assertNotIn("route-scan", CSS)
        self.assertIn(".recovery-note {", CSS)
        reduced = CSS[CSS.index("@media (prefers-reduced-motion: reduce)"):]
        self.assertIn(".route-gate-ring,", reduced)

    def test_runtime_identities_remain_readable_and_discoverable(self):
        render = JS.split("function renderControl()", 1)[1].split("function recoverControlPending", 1)[0]
        self.assertIn("const profileIdentity =", render)
        self.assertIn("const emulatorIdentity =", render)
        self.assertIn("const versionIdentity =", render)
        self.assertIn("$(id).title = identity;", render)
        facts = CSS.split(".engine-facts dd {", 1)[1].split("}", 1)[0]
        self.assertIn("overflow-wrap: anywhere;", facts)
        self.assertNotIn("text-overflow: ellipsis", facts)
        self.assertNotIn("white-space: nowrap", facts)

    def test_evidence_view_explains_issued_observed_and_proven_states_visually(self):
        for token in (
            'class="evidence-runway"',
            "A click is not a result.",
            "Input delivery was accepted once.",
            "The expected screen transition appeared.",
            "Identity, state, and Home return agree.",
            'class="evidence-node evidence-node-proven"',
        ):
            self.assertIn(token, HTML)
        self.assertIn(".evidence-runway {", CSS)
        self.assertIn(".evidence-node-proven { color: var(--success); }", CSS)

    def test_apply_then_start_is_enforced_in_both_render_and_command_paths(self):
        render = JS.split("function renderControl()", 1)[1].split("function recoverControlPending", 1)[0]
        send = JS.split("async function sendControl(action)", 1)[1].split("function eventDate", 1)[0]
        self.assertIn("clientProblems(SAVED)", render)
        self.assertIn("allSettings().some(isUnsaved)", send)
        self.assertIn("!PLAN_WRITTEN", send)
        self.assertIn("clientProblems(SAVED).length", send)
        self.assertNotIn("savePlan()", send)
        self.assertIn("CONTROL_PENDING = { action, request_id: null", send)
        self.assertIn('id="savedPlanHash"', HTML)
        self.assertIn('id="visiblePlanHash"', HTML)
        self.assertIn("crypto.subtle.digest('SHA-256'", JS)
        self.assertIn("The applied plan is locked until the active run stops.", JS)

    def test_native_profile_mode_is_explicit_recoverable_and_visibly_auto_launches(self):
        render = JS.split("function renderControl()", 1)[1].split("function recoverControlPending", 1)[0]
        send = JS.split("async function sendControl(action)", 1)[1].split("function capabilityLabel", 1)[0]
        self.assertIn('id="controlNativeMode"', HTML)
        self.assertIn("NATIVE_PROFILE_MODE", render)
        self.assertIn("BlueStacks and Clash of Clans will be launched if needed", render)
        self.assertIn("action === 'start' && !NATIVE_PROFILE_MODE", send)
        self.assertIn("fetch('/api/plan/native'", send)
        self.assertIn("NATIVE_PROFILE_MODE = false", JS.split("async function savePlan()", 1)[1])
        self.assertIn(".engine-actions #controlNativeMode { grid-column: 1 / -1; }", CSS)
        self.assertIn("Native profile guarded start", JS)
        self.assertIn("Apply this draft to leave full profile automation.", JS)
        self.assertIn("$('runValidation').hidden = nativeCopy", JS)

    def test_targeted_surfaces_are_filtered_aliases_not_copied_controls(self):
        self.assertIn("settingIds: ['run.surface', 'run.strategy']", JS)
        self.assertIn("Builder Base is visible here only as a blocked route", JS)
        self.assertIn("builderBaseUnavailableReason()", JS)
        self.assertIn("The controls below are shown for review only; Start remains blocked.", JS)
        self.assertIn("sectionIds: ['search', 'limits', 'resources']", JS)
        self.assertIn("settingIds: ['upgrade.policy', 'events.laboratory']", JS)
        self.assertIn("settingIds: ['account.queue']", JS)
        self.assertIn("settingIds: ['runtime.emulator', 'runtime.instance', 'notify.on_stop', 'notify.on_error', 'notify.channel']", JS)
        self.assertIn("These controls use the same persisted planner values as Run Planner.", JS)
        self.assertIn("groupNav.hidden = !!planSurface.settingIds || !!planSurface.sectionIds;", JS)
        self.assertNotIn("id=\"viewBuilder", HTML)

    def test_safe_home_starting_point_does_not_impersonate_native_profile_mode(self):
        render = JS.split("function renderControl()", 1)[1].split("function recoverControlPending", 1)[0]
        self.assertIn('id="controlSafeHomeRoute"', HTML)
        self.assertIn('class="route-prepare"', HTML)
        self.assertIn("$('controlNativeMode').onclick = activateNativeProfileMode;", JS)
        self.assertIn("$('controlSafeHomeRoute').onclick = prepareVerifiedHomeRoute;", JS)
        self.assertIn("$('controlSafeHomeRoute').disabled = !BOOT_READY || busy || !connected || state !== 'idle';", render)
        self.assertIn("Nothing is applied or started.", HTML)
        self.assertIn(".route-prepare {", CSS)
        self.assertNotIn("every enabled native profile setting", JS)

    def test_conditional_invalid_combinations_are_recoverable(self):
        self.assertIn("emulator === 'auto' && instance", JS)
        self.assertIn("emulator !== 'auto' && !instance", JS)
        self.assertIn("plan['run.strategy'] === 'smart.local' && !plan['run.diagnostic_mode']", JS)
        self.assertIn("PLAN[id] === defaultFor(setting)", JS)
        self.assertIn("PLAN[id] === 'profile-current'", JS)
        self.assertIn("Number.isInteger(number)", JS)
        self.assertIn("must use increments of ${rules.step}", JS)

    def test_native_activity_is_proof_friendly_not_a_fake_wall_clock(self):
        event_date = JS.split("function eventDate(event)", 1)[1].split("function humanizeEventType", 1)[0]
        self.assertNotIn("timestamp_ms ??", event_date)
        self.assertIn("function elapsedEventTime(event)", event_date)
        self.assertIn("+${Math.round(elapsed)}ms", event_date)
        self.assertIn("time.dateTime = `PT${elapsed / 1000}S`", JS)
        self.assertIn("['error', 'warning', 'info', 'debug']", JS)


if __name__ == "__main__":
    unittest.main()
