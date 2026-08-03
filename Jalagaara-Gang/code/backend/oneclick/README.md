# oneclick — run the backend without the ceremony

Each `.ps1` finds the project's Python for you (no `activate` needed) and runs one thing. Call them
from the repo root. **Only prerequisite:** you've done the one-time setup once (see
[../README.md](../README.md) → Setup) so `backend\.venv` exists.

| Script | What it does |
|---|---|
| `backend\oneclick\detect.ps1` | Detect an anomaly for a metric at an hour |
| `backend\oneclick\compare.ps1` | Run both detectors (robust_z vs seasonal_ml) side by side |
| `backend\oneclick\tables.ps1` | List ClickHouse tables + row counts (is the DB alive?) |
| `backend\oneclick\test.ps1` | Run the whole test suite |
| `backend\oneclick\api.ps1` | Start the API on http://localhost:8000 (dev console at `/dev`) |
| `backend\oneclick\load.ps1` | Load ALL data into ClickHouse via CLI (reliable path for the 9M-row job) |

## Examples
```powershell
.\backend\oneclick\detect.ps1
.\backend\oneclick\detect.ps1 --metric fill_rate --at 2026-06-29T10:00 --method seasonal_ml
.\backend\oneclick\compare.ps1 --metric revenue --at 2026-07-04T10:00
.\backend\oneclick\tables.ps1
.\backend\oneclick\test.ps1
```

`detect` / `compare` accept:
- `--metric` — `revenue | fill_rate | ctr | ecpm | rpr | render_rate` (default `revenue`)
- `--at` — the target hour, ISO format `YYYY-MM-DDThh:mm` (default `2026-07-04T10:00`)
- `--method` (detect only) — `robust_z` or `seasonal_ml`; overrides `config.json` just for this run

> If PowerShell refuses to run a script, allow it for the current window once:
> `Set-ExecutionPolicy -Scope Process -Bypass`

## Prefer no PowerShell wrapper?
From `backend\` with the venv active, the same launchers are plain modules:
```bash
python -m oneclick.detect --metric revenue --at 2026-07-04T10:00
python -m oneclick.compare
python -m oneclick.tables
```
