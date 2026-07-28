# Sprint 3 diagnostics canvas

Regenerate the visual bundle (PNGs + `traces.json` + `index.html`):

```bash
MPLBACKEND=Agg PYTHONPATH=src python scripts/generate_diagnostics_canvas.py --out diagnostics
```

Open `diagnostics/index.html` in a browser. Each figure has paired numerical
assertions in `tests/diagnostics/test_diagnostics.py`.
