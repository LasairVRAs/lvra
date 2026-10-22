# Testing Plan

Prioritize production LVRA runtime tests around Kafka ingestion, feature generation, prediction, annotation, and cron/bash orchestration. Centralize the SQLite schema first, then use that schema in integration tests so tests track production tables instead of duplicating them.

## Scope

- In: `bash/bigbashboy.sh`, production bash wrappers, `lvra/pypeline/kafka_consumer.py`, `lvra/pypeline/r0b_feature_maker.py`, `lvra/pypeline/r0b_predict.py`, `lvra/pypeline/r0b_annotator.py`, `lvra/utils/misc.py`, `lvra/utils/features.py`, `lvra/utils/predict.py`, production config shape, SQLite schema setup, and tests under `test/`.
- Out: `lvra/training/*`, model-quality validation, retraining workflows, ML experiment management, and `lvra/utils/tns.py`.

## Action Items

[x] Add a central schema file, e.g. `data/log_schema.sql`, containing the production `feature_making`, `annotating`, `predict`, `diaobjid_stems`, `provenance`, and `threshold_flags_provenance` table definitions.

[x] Add a small test helper, e.g. `test/conftest.py`, that creates a temporary SQLite `log.db` from `data/log_schema.sql` using `sqlite3.executescript()`.

[x] Refactor existing integration-style tests in `test/test_pypeline_r0bfeatures.py`, `test/test_pypeline_r0bpredict.py`, `test/test_pypeline_r0bannotator.py`, and `test/test_kafka_consumer.py` to use the schema helper instead of hard-coded table setup.

[x] Strengthen `lvra/utils/features.py` tests for production data edge cases: missing/null `alert`, duplicate `diaObjectId`, empty `diaSourcesList`, mismatched joined IDs, threshold flag correctness, and malformed input JSON.

[x] Strengthen `lvra/pypeline/kafka_consumer.py` tests for zero-message runs, byte/string payloads, Kafka errors, invalid JSON, atomic temp-file behavior, SQLite initialization rows, duplicate `diaObjectId`, and finalization failures.

[x] Strengthen `lvra/pypeline/r0b_feature_maker.py` tests for missing JSON, partial feature success, threshold provenance failures, feature status-code mapping, path construction from stems, and SQLite commit/close behavior.

[x] Strengthen `lvra/pypeline/r0b_predict.py` and `lvra/utils/predict.py` tests for missing model config, missing model file, missing CSV, missing model features, bad `predict_proba` output, provenance inserts, and predict-table status updates.

[x] Strengthen `lvra/pypeline/r0b_annotator.py` tests for missing token, Lasair client construction failure, no pending annotations, mixed annotation success/failure, missing threshold flags, duplicate threshold rows, and annotating-table status updates.

[x] Add one end-to-end integration test that runs the local production flow against temp files and schema-backed SQLite: fake Kafka messages -> JSON file -> feature CSV -> prediction provenance -> mocked Lasair annotation.

[x] Update CI to report `pytest --cov=lvra --cov-report=term-missing` without enforcing a coverage threshold yet; target 90% production-module coverage as the working goal.

## Notes

- Keep `lvra/utils/tns.py` out of the handoff-critical testing push because the incoming developer owns TNS-specific code.
- Use `data/log_schema.sql` as the canonical schema for integration tests to avoid schema drift between test setup and production.
