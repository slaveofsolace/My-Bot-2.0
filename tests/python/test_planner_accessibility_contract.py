import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
HTML = (ROOT / "ui" / "planner.html").read_text(encoding="utf-8")
JS = (ROOT / "ui" / "planner.js").read_text(encoding="utf-8")
CSS = (ROOT / "ui" / "planner.css").read_text(encoding="utf-8")


class PlannerAccessibilityContract(unittest.TestCase):
    def test_heartbeat_is_not_repeated_through_live_region(self):
        self.assertIn('id="controlAck"', HTML)
        self.assertNotIn('id="controlAck" aria-live', HTML)
        self.assertIn('id="controlAnnouncement" aria-live="polite"', HTML)
        self.assertIn("if (!text || text === LAST_CONTROL_ANNOUNCEMENT) return", JS)

    def test_boot_is_fail_closed_and_has_a_retry_shell(self):
        for control_id in (
            "controlStart", "controlPause", "controlStop", "viewRunButton",
            "viewPlanButton", "viewDiagnosticsButton", "apply", "reset",
            "filter", "presetSelect", "exportDiagnostics",
        ):
            marker = f'id="{control_id}"'
            tag = HTML[HTML.rfind("<", 0, HTML.index(marker)):HTML.index(">", HTML.index(marker))]
            self.assertIn("disabled", tag, control_id)
        self.assertIn('id="bootRetry" type="button" hidden', HTML)
        self.assertIn("function showBootFailure(error)", JS)
        self.assertIn("No plan or command was sent.", JS)
        self.assertIn("const [metadataPayload, plan, health] = await Promise.all([", JS)

    def test_revert_is_outside_the_label_and_redraw_restores_focus(self):
        self.assertIn("titleLine.append(label);", JS)
        self.assertIn("titleLine.append(revert);", JS)
        self.assertNotIn("label.append(revert)", JS)
        self.assertIn("document.getElementById(focusId) || fallback", JS)

    def test_arrow_navigation_moves_focus_without_synthetic_activation(self):
        body = JS.split("function handleRovingKeys(event, buttons)", 1)[1].split("const viewButtons", 1)[0]
        self.assertIn("buttons[next].focus()", body)
        self.assertNotIn(".click()", body)

    def test_hero_chips_form_a_named_group(self):
        self.assertIn("field.setAttribute('role', 'group')", JS)
        self.assertIn("field.setAttribute('aria-labelledby', label.id)", JS)
        self.assertIn("chip.id = `f_${setting.id}_${option.value}`", JS)
        self.assertIn("chip.setAttribute('aria-pressed', String(selected))", JS)

    def test_details_activity_and_plan_receipt_survive_small_layouts(self):
        self.assertIn('id="rawLogDetails"', HTML)
        self.assertIn('id="events"', HTML)
        self.assertIn('class="plan-receipt"', HTML)
        self.assertIn(".plan-receipt { position: static; grid-column: 1 / -1; }", CSS)
        mobile = CSS[CSS.index("@media (max-width: 700px)"):]
        self.assertIn(".plan-groups { grid-template-columns: repeat(2, minmax(0, 1fr));", mobile)
        self.assertIn("@media (max-width: 360px)", mobile)
        self.assertNotIn(".raw-log { display: none", mobile)

    def test_activity_exposes_real_severity_and_machine_readable_time(self):
        self.assertIn("['error', 'warning', 'info', 'debug'].includes(event.severity)", JS)
        self.assertIn("time.dateTime = date.toISOString()", JS)
        self.assertIn("elapsedEventTime(event)", JS)
        for severity in ("error", "warning", "info", "debug"):
            self.assertIn(f".activity-severity.{severity}", CSS)
        self.assertIn("['rejected', 'failed'].includes(outcome) ? 'error' : 'info'", JS)

    def test_capability_perimeter_is_truthful_data_driven_and_nonduplicative(self):
        self.assertIn('class="capability-overview" aria-labelledby="capabilityOverviewTitle"', HTML)
        self.assertIn('id="capabilityOverviewSummary"', HTML)
        self.assertIn('class="capability-perimeter" aria-hidden="true"', HTML)
        for state in ("Supported", "Implemented", "Inherited", "Gated"):
            self.assertIn(f'id="capabilityCount{state}"', HTML)
            self.assertIn(f'id="capabilityGraphic{state}"', HTML)
            self.assertIn(f'id="capabilitySignal{state}"', HTML)
        body = JS.split("function renderCapabilityOverview(capabilities)", 1)[1].split(
            "function renderCapabilities()", 1
        )[0]
        self.assertIn("const surfaced = capabilities.filter", body)
        self.assertIn("capabilityPublicState(capability.status)", body)
        self.assertIn("$(`capabilitySignal${state}`)", body)
        self.assertIn("the release evidence gate is reported separately below", body)
        self.assertNotIn("Support remains at 0", body)
        self.assertIn(".perimeter-core-boundary", CSS)
        self.assertNotIn("capability-radar", CSS)

    def test_release_evidence_snapshot_is_data_driven_and_fail_closed(self):
        for element_id in (
            "evidenceHistoricalReady", "evidenceExactCurrentReady",
            "evidenceVerifiedFixtures", "evidenceReadinessNote",
        ):
            self.assertIn(f'id="{element_id}"', HTML)
        body = JS.split("function renderEvidenceReadiness(summary)", 1)[1].split(
            "function renderCapabilityOverview(capabilities)", 1
        )[0]
        self.assertIn("summary?.historical_ready_for_review", body)
        self.assertIn("summary?.exact_current_ready_for_review", body)
        self.assertIn("summary?.fixture_inventory", body)
        self.assertIn("summary?.valid === true", body)
        self.assertIn("failed closed", body)
        self.assertNotRegex(body, r"\b9\s*/\s*61\b")
        self.assertNotRegex(body, r"\b0\s*/\s*61\b")
        self.assertIn("EVIDENCE_READINESS = metadataPayload.evidence_readiness || null;", JS)
        self.assertIn(".evidence-readiness-values {", CSS)

    def test_capability_ledger_cannot_silently_omit_new_catalog_entries(self):
        grouping = JS.split("function capabilityGroupsForCatalog(capabilities)", 1)[1].split(
            "function renderCapabilityOverview(capabilities)", 1
        )[0]
        self.assertIn("const catalogIds = capabilities.map", grouping)
        self.assertIn("const assigned = new Set(CAPABILITY_GROUPS.flatMap", grouping)
        self.assertIn("catalogIds.filter(id => !assigned.has(id))", grouping)
        self.assertIn("Additional inventoried scope", grouping)
        renderer = JS.split("function renderCapabilities()", 1)[1].split("function eventDate", 1)[0]
        self.assertIn("const groups = capabilityGroupsForCatalog(capabilities);", renderer)
        self.assertIn("renderCapabilityOverview(capabilities);", renderer)
        self.assertIn("for (const group of groups)", renderer)
        self.assertIn("row.dataset.capabilityId = id;", renderer)

    def test_theme_supports_system_light_and_dark_without_effect_layers(self):
        self.assertIn('<option value="system">System</option>', HTML)
        self.assertIn('<option value="light">Light</option>', HTML)
        self.assertIn('<option value="dark">Dark</option>', HTML)
        self.assertIn(':root[data-theme="dark"]', CSS)
        self.assertIn("@media (prefers-color-scheme: dark)", CSS)
        self.assertNotIn("gradient", CSS.lower())
        self.assertNotIn("backdrop-filter", CSS.lower())

    def test_visible_theme_and_text_controls_keep_touch_size(self):
        self.assertIn(".text-button {\n  min-height: 44px;", CSS)
        self.assertIn(".theme-control select { min-width: 88px; min-height: 44px;", CSS)

    def test_compact_controls_keep_full_touch_targets(self):
        self.assertRegex(CSS, r"\.revert\s*\{[^}]*min-height:\s*44px")
        self.assertRegex(CSS, r"\.switch\s*\{[^}]*min-height:\s*44px")
        self.assertRegex(CSS, r"\.switch input\s*\{[^}]*height:\s*44px")
        self.assertRegex(CSS, r"\.chip\s*\{[^}]*min-height:\s*44px")
        self.assertRegex(CSS, r"\.setting-help summary\s*\{[^}]*min-height:\s*44px")
        self.assertRegex(CSS, r"\.raw-log summary\s*\{[^}]*min-height:\s*44px")


if __name__ == "__main__":
    unittest.main()
