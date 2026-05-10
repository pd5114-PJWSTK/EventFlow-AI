# Active Test Suite

`tests/` contains the production regression suite used before VPS deployment.

Run it through the canonical Docker quality gate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\run-quality-gates.ps1
```

Kept active:

- Core health, auth and job tests.
- Phase 7 end-to-end workflow coverage.
- Phase 8 planner, runtime, frontend-contract and ML regressions.
- Phase 9 operations monitoring checks.

Historical Phase 2-6 checkpoint tests are archived in `non_production/checkpoint_tests/` and are excluded from default pytest discovery by `pytest.ini`.
