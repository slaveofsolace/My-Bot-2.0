# Run Planner interface

Captured from `tools/planner_ui.py` at 1340×780. Re-shoot them when the interface changes:

```bash
python tools/planner_ui.py --port 8802 --no-browser &
chromium --headless --virtual-time-budget=6000 --window-size=1340,780 \
  --screenshot=docs/ui/screenshots/planner-heroes.png http://127.0.0.1:8802/#heroes
```

`--virtual-time-budget` matters. Without it the shot lands before the page has fetched its metadata
and you get a picture of the word "Loading".

## planner-heroes.png

The Hero picker. Six Heroes, four active slots, the ceiling enforced in the control rather than
discovered when the engine refuses the plan.

## planner-pacing.png

Pacing, with several settings changed from their defaults — which is what the outlines, the per-section
counts in the sidebar, and the `revert` controls are showing.
