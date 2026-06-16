# Test Suite Review

**143 tests across 13 files.** Coverage is genuinely solid for a research pipeline. The integration test, pipeline `main()` tests with monkeypatching, and the `utils/predict.py` suite are all well-done. But Pyright surfaced a few real issues, and there are meaningful gaps.

---

## Pyright-found bugs (fix these, not just add tests)

### 1. `tns.py:373` — subscripting a possible integer
```python
report_id = str(json.loads(summary['response_text'])['data']['report_id'])
```
`report2TNS()` can return `99` (int) on error. If it does, `summary['response_text']` crashes. This is inside `test_tns_report_dictionary()` in the source file itself, so production risk is low — but it's dead code that should either be deleted or fixed.

### 2. `r0b_annotator.py:129` — `flags_dict` possibly unbound (confusing control flow)
```python
# elif len(flags) > 1: → logs but doesn't assign flags_dict
# then: if len(flags) >= 1: → always covers that branch
```
The logic is actually sound, but Pyright can't see through it and neither can a reader. The test `test_get_threshold_flags_uses_latest_duplicate_row` covers the `> 1` branch but it works by coincidence of the second `if` block. Worth restructuring for clarity — no test needed, just a refactor.

### 3. `learning_utils.py:200` — `mapping` dict has `None`/`np.nan` keys and `np.nan` values
The type declared is `Dict[str, int] | None` but the default mapping has non-string keys and non-int values. Functionally works because pandas `.map()` is tolerant, but the declared type is wrong and could mask bugs in mapping-validation code.

---

## Test coverage gaps (prioritised)

### Priority 1 — `flux_threshold_features()` has no unit tests
`lvra/utils/features.py:56`

This is the core feature computation logic (threshold crossings, first-time flags) and it's only exercised indirectly through `json2cleandf`. The branching logic around `n_above == 1` and the `np.isclose` check on the latest MJD is non-trivial. Add direct tests for:
- all fluxes below threshold → `n_above=0`, both flags `None`
- exactly one detection above threshold, and it's the latest → `first_time_flag=True`
- one detection above threshold but it's *not* the latest → `first_time_flag=False`
- multiple detections above threshold → `first_time_flag=False`

### Priority 2 — `nsr_sampling2` fallback with `Nlow=0` is likely broken
`lvra/training/sampling.py`

```python
midN = sorted_predictions.iloc[Nhi:-Nlow].diaSourceId.sample(Nmid).values
```
`-0 == 0` in Python, so `iloc[Nhi:-0]` = `iloc[Nhi:0]` = empty slice. Add a test:
```python
sampling.nsr_sampling2(..., Nlow=0, ...)  # likely raises ValueError: cannot sample > population
```

### Priority 3 — `set_up()` env var override not tested
`lvra/utils/misc.py`

`LVRA_DATA_ROOT` overrides `base_dir` from the YAML, but `TestSetUpFunction` never sets that env var. One test with `monkeypatch.setenv('LVRA_DATA_ROOT', str(tmp_path))` verifies the whole env-override path.

### Priority 4 — `json2cleandf` doesn't test `deltaDiaSourceMjdTai`
`lvra/utils/features.py:91`

The integration test uses `deltaDiaSourceMjdTai` as the sole model feature, but `test_utilsfeatures.py` never asserts it's present or correct. Add a check that `lastDiaSourceMjdTai - firstDiaSourceMjdTai` computes correctly for a two-source alert.

### Priority 5 — `test_utilsmisc.py` mocking is leaky
`test/test_utilsmisc.py`

The `TestSetUpFunction` tests mock `lvra.utils.misc.logging` but `logging.basicConfig()` is called on the real module. This can create log files in `/tmp/test_base/...` during the test run (or fail silently on permission errors). Use `tmp_path` for `base_dir` in all those tests (some already do, some don't), and avoid mocking the entire `logging` module.

---

## What's well-covered (no action needed)

- `utils/predict.py` — thorough, including edge cases and error codes
- `pypeline/r0b_predict.py` — good `main()` coverage via monkeypatching
- `training/learning_utils.py` — all 7 public functions tested
- `training/labeling.py` — `interactive_labeling` with keyboard interrupt, resume, invalid labels
- `pypeline/r0b_feature_maker.py` — `threshold_flags_provenance`, `main()`, and missing-JSON paths all covered
- Integration test — exercises the full Kafka→features→predict→annotate chain
