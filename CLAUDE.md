# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Principles
- Prefer the simplest solution that works — no over-engineering
- Minimize compute: prefer cheap operations, avoid unnecessary passes, loops, or redundant work
- Be concise: no explanations unless explicitly asked
- No comments unless the WHY is non-obvious
- No new abstractions unless clearly justified by the task

## Code style
- If asked for a solution, provide the code directly — no preamble, no walkthrough
- Do not add error handling, fallbacks, or validation beyond what the task requires
- Do not add features or refactor beyond the scope of the request
- No docstrings unless explicitly asked; when asked, use NumPy style
- No comments unless explicitly asked

## Safety
- Do not run code unless explicitly asked

## Commands

### Testing
```bash
pytest test/                          # run all tests
pytest test/test_foo.py               # run a single test file
pytest test/test_foo.py::test_bar     # run a single test
pytest -m "not slow and not integration"  # skip slow/integration tests
pytest --cov=lvra --cov-report=html   # with coverage
```

### Install
```bash
pip install -e ".[dev]"   # editable install with test dependencies
```

## Architecture

**Lasair VRA** is a pipeline that classifies astronomical transients (from LSST/Rubin via Lasair) using a trained ML model (scikit-learn, joblib-serialized).

### Production pipeline (`lvra/pypeline/`)
Three sequential stages, each run as a separate script with its own `main()`:

1. **`kafka_consumer.py`** — polls Lasair Kafka for alert JSON, writes timestamped `.json` files to `$base_dir/JSON/YYYY/YYYYMMDD/`
2. **`r0b_feature_maker.py`** — reads JSON alerts, computes features, writes `.csv` files to `$base_dir/csv/YYYY/YYYYMMDD/`
3. **`r0b_predict.py`** — loads CSVs, runs model, writes scores to the SQLite `provenance` table
4. **`r0b_annotator.py`** — reads `provenance` and pushes scores back to Lasair via API

Progress through the pipeline is tracked in a SQLite log DB (`$base_dir/db/log.db`) with tables: `feature_making`, `predict`, `annotating`, `provenance`, `diaobjid_stems`. Status values: `1` = success, `-1` = some failure, `21` = file not found, `99` = unknown error.

File stems (e.g. `20260127_115934`) identify a poll batch. The log DB schema lives in `data/log_schema.sql`; test fixtures create it via `test/helpers.py:initialise_log_db`.

### Utilities (`lvra/utils/`)
- `misc.py` — `set_up()` builds the runtime directory structure and logger from a YAML settings file; `read_model_config()` loads model YAML; `check_pckg_versions()` guards against conda env drift
- `features.py` — feature computation logic
- `predict.py` — wraps model `.predict_proba()` into a scored DataFrame
- `tns.py` — TNS (Transient Name Server) lookups

### Training (`lvra/training/`)
Offline scripts for building the training pool and fitting models:
- `make_pool.py` — aggregates CSV feature files into `X_pool.parquet`; deduplicates via SHA-256 of source files
- `labeling.py` — assigns labels to pool objects
- `sampling.py` — sampling strategies for active learning
- `learning_utils.py` — config loading, parquet loading, shared training helpers

### Configuration
Settings are resolved via environment variables (preferred) then fallback files:
- `LVRA_SETTINGS` → path to settings YAML (default: `data/public_settings.yaml`)
- `LVRA_R0B_CONFIG` → path to model config YAML (default: `data/r0b_config.yaml`)
- `LVRA_DATA_ROOT` → base directory for all runtime data
- `LVRA_TRAINING_ROOTDIR` → root for training data (`csv/`, `pool/`, `logs/`)
- `LASAIR_TOKEN` → API token for Lasair annotation push
