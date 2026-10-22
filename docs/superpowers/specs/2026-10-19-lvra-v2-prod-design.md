# LVRA v2 in production — design

Date: 2026-10-19 · Status: draft for H's review · Oversight mode for the build: collab (TDD)

## Intent

Rubin alerts restart in ~2 weeks. The retraining work in `~/Science/r0b-retraining` produced a
champion: a 5-class multiclass classifier (`class_weight="balanced"`, all ~150 features, trained on
the even sample, `retraining_exploration2/`). It beats prod r0b clearly (Purity@n_pos 0.69 vs 0.42).
We want it live, as a **second annotator running alongside `r0b_lvra`**, built to last: it must be
able to carry several models at once (champion / challenger / retired) and expose useful
lightcurve features to Lasair users, without needing a new annotator per model.

The prod code is written fresh, line by line, in collab mode with TDD: H reads and comments all of
it, and tests prove the numbers match the training features.

## Goals

1. A new annotator (topic name TBD by H) whose `classdict` holds every model slot and a set of public features.
2. A small feature store (`features.db`, SQLite) recording every alert's features and every model's scores, built to migrate to MariaDB within ~6 months.
3. A new feature → predict → annotate chain that runs concurrently with r0b and shares only the Kafka consumer and its JSON files.
4. Prod features provably equal to training features (parity test on a real raw alert).

## Non-goals

- Touching the r0b chain (`r0b_feature_maker.py`, `r0b_predict.py`, `r0b_annotator.py`, `provenance`, `threshold_flags_provenance`). r0b keeps running unchanged.
- Training code in this repo. The champion `.joblib` comes from r0b-retraining; training stays out of prod code.
- MariaDB, historical backfill of old JSON/CSVs, refactoring r0b and the new chain into one. All deferred to the "Big Refactor".
- Batched annotation (`annotate_list`). The LSST server applies a batch item by item and stops at the first error, leaving a half-applied batch; one `L.annotate` per object, as r0b does.

## Anti-goals (failure even if it runs)

- r0b annotations break or stop during the rollout.
- Prod features silently differ from the features the champion was trained on.
- A `classdict` over Lasair's 4096-character limit, or a `classification` string that sorts wrongly.
- Code H hasn't read and commented.

## Constraints

- Lasair-LSST annotation limits (from `lsst-uk/lasair-lsst` `webserver/lasairapi/serializers.py`): `classification` ≤ 80 chars, `classdict` ≤ 4096 chars as JSON text, `version` ≤ 80, all fields required (`explanation`, `url` may be blank).
- `classification` is stored as text: `ORDER BY` sorts alphabetically.
- Filters read `classdict` with `JSON_EXTRACT(<topic>.classdict, '$.a.b')`; nested paths work in Lasair-LSST (docs example: `'$.lsst-r.absolute_peak_mag_val' < -19`).
- Volume: ~70k objects/night × 2–3 alerts ≈ 200k feature rows/night, ~1.5 KB each → ~300 MB/night, ≤ ~45 GB over the ≤ 6 months on SQLite.
- Champion pickled with sklearn 1.8 (`lvra` env); prod env must match (`check_pckg_versions()`).
- Two weeks to first alerts.

## Decisions (H's)

### 1. Annotator

- One `L.annotate` call per object.
- `classification` = champion's `extragal` probability, formatted `f"{p:.6f}"` (fixed 6 decimals, never scientific notation, so text ordering is correct).
- `version` = champion's model version.
- `classdict` is **nested by model slot**, all floats rounded to 6 significant figures (`round` is fine inside the JSON; only `classification` needs the fixed format):

  ```json
  {
    "champion":   {"version": "...", "extragal": 0.912345, "mover": ..., "real": ..., "bogus": ..., "agn": ...},
    "challenger": null,
    "retired":    null,
    "n_gt22": 3, "brighter22": true, "first22": false,
    "...": "remaining public features at top level"
  }
  ```
- *(Names superseded — see Open item 3, 2026-10-21 and 2026-10-22.)* Threshold features keep **r0b's names** (`n_gtXX`, `brighterXX`, `firstXX`) for backwards compatibility with existing filters such as `JSON_EXTRACT(r0b_lvra.classdict, "$.first22")`. They are the same quantities as the training CSV's `N_above_XX`, `is_above_XX`, `first_time_XX` (both follow `lvra.utils.features.flux_threshold_features`).
- Public features (draft, H to confirm in the README):
  - `n_gtXX`, `brighterXX`, `firstXX` for XX ∈ {18, 19, 20, 21, 22}
  - `n_loR_sources`, `n_hiR_sources`
  - `max_flux`, `delta_days_SINCE_MAX`, `delta_days_TO_MAX`, `delta_days_TOTAL`
  - `current_snr`
  - `n_det_{b}`, `n_det_snr10_{b}` for b ∈ {u, g, r, i, z}
- Promotion (challenger → champion → retired) is a config edit, not a code change.

### 2. Feature store — `features.db` (SQLite, WAL mode, separate from `log.db`)

Plain SQL, explicit typed columns, nothing SQLite-specific, so moving to MariaDB is
"create the same tables, copy rows, change connection".

- `features`: `diaSourceId` PRIMARY KEY (the alert's latest/trigger source), `diaObjectId` (indexed), `stem` (indexed), `timestamp`, then one column per feature. One row per alert, never overwritten: insert with `INSERT OR IGNORE` (first write wins; mirrors the MariaDB plan's `INSERT IGNORE`).
- `model_scores`: `diaSourceId` (`REFERENCES features(diaSourceId)`), `diaObjectId`, `stem`, `model_role` (champion/challenger/retired), `model_version`, one column per class `extragal`, `mover`, `real`, `bogus`, `agn`, `gal` (`gal` NULL for this model version), `timestamp`. One row per alert per model. Connections run `PRAGMA foreign_keys = ON`.

### 3. Pipeline — a separate chain alongside r0b

```
kafka_consumer.py ─► JSON/YYYY/YYYYMMDD/<stem>.json
                      ├─► r0b_feature_maker ─► r0b_predict ─► r0b_annotator   (unchanged)
                      └─► lvra_feature_maker ─► lvra_predict ─► lvra_annotator (new)
                              │                    │                 │
                              ▼                    ▼                 ▼
                       features.db:features  features.db:model_scores  Lasair
```

- `lvra_feature_maker.py`: reads each new stem's JSON, computes features with the same semantics as `r0b-retraining/scripts/make_lc_feature_rows.py`, writes `features`. We WILL NOT Rreuse `json2cleandf` but we can reuse `flux_threshold_features` from `lvra/utils/features.py`. `sherlock_*` columns come from the JSON (filter output).
- `lvra_predict.py`: scores each stem's rows with every model present in the config (champion, plus challenger/retired when set), writes `model_scores`.
- `lvra_annotator.py`: per object, latest scores + features → `classdict` → `L.annotate`.
- Progress tracking: add an `lvra` status column to `log.db`'s `feature_making`, `predict`, `annotating` (same status codes as `r0b`: 1, -1, 21, 99).
- A new model config YAML (alongside `data/r0b_config.yaml`) naming model path + version for each slot, plus `TOPIC_OUT`, `EXPLANATION`, `URL`.
- The champion `.joblib` is produced in r0b-retraining and copied to the prod models directory.

### 4. Testing

- TDD throughout, collab mode.
- **Parity test**: H extracts a raw alert JSON (from the remote servers) for an object in the training set; the fixture's features from `lvra_feature_maker` must equal that alert's row in the training CSV. It catches mistakes in going from JSON to `features.db` rows and in reading features back out for the model.
- `sherlock_*` mapping from the JSON filter output (`z`, `photoZ`, `separationArcsec`, ...): the JSON is the only source of these columns; H checks the mapping by hand.
- `classdict` serialised length < 4096 with all three slots filled; `classification` formatting (small values stay `0.0000xx`).

## Open items (H)

1. **Annotator topic name.**
2. **Example JSON with forced photometry** (H to supply). Decided: `rise_rate_{b}` stays on forced photometry as trained (`make_lc_feature_rows.py:382`–`385`); low importance and forced photometry should now be in every alert.
3. **Public feature list**: confirm names and band coverage in the README draft.
   - *Decided 2026-10-21 (H):* `n_gtXX`, `everbrighterXX` (renamed from r0b's `brighterXX`: "brighter" read as "brighter now"), `firstXX` for XX = 18–23; `n_loR_sources`, `n_hiR_sources` (R stays upper case); `max_flux`, `delta_days_since_max`, `delta_days_to_max`, `delta_days_total` (lower case); `current_snr`; `n_det_{b}`, `n_det_snr10_{b}` for b = u, g, r, i, z, y. r0b filters are unaffected (r0b keeps annotating `r0b_lvra` with its old names). Latest alert per object = latest stem, then max `delta_days_TOTAL` within a stem (same `firstDiaSourceMjdTai`).
   - *Amended 2026-10-22 (H), after inspecting real classdicts from the dev dry run:* threshold names made consistent and short (no autocomplete on JSON fields): `n_gtXX`, `ever_gtXX` (was `everbrighterXX`), `first_gtXX` (was `firstXX`). `n_loR_sources` and `n_hiR_sources` now come straight after the model slots (`retired`), before `n_gt18`, because every field after them is computed on hiR sources only. Classdict order: `blame_diaSourceId`, `champion`, `challenger`, `retired`, `n_loR_sources`, `n_hiR_sources`, threshold features, then the rest.
4. **Disk**: run `df -h $LVRA_DATA_ROOT` on prod to confirm ~45 GB headroom.

## My calls (Claude's; H to check)

- `model_scores` stores one column per class; a future model with different classes needs an `ALTER TABLE`.
- `classdict` model slots contain only the classes the model outputs (`gal` omitted while it's NULL) to save characters; empty slots are `null`.
- The `features` table stores every column the feature maker computes (training CSV superset, keyed per alert), not only the model's `feature_names_in_`; the training-CSV names are kept in the table (`N_above_22`, ...) and the annotator maps them to r0b's names.
- `distance`, `absMag`, `absMagMJD` were NaN throughout training (not in Cassandra). If any are in the champion's `feature_names_in_`, prod feeds NaN for them even if the JSON has values, to match training.
- Which alerts get annotated per run mirrors r0b: an object's latest scored alert in the pending stems.
- A retired model keeps being scored until it is removed from the config; no automatic expiry.
- The `log.db` `lvra` columns go in via `ALTER TABLE ... ADD COLUMN` on the existing prod `log.db` (`CREATE TABLE IF NOT EXISTS` in `log_schema.sql` will not add them); `log_schema.sql` is updated for fresh installs. This touches prod and is its own checkpoint.

## Left to the builder

File layout inside `lvra/` (new pypeline scripts vs shared utils), cron cadence (mirror r0b's), logging format (mirror r0b's), how `json2cleandf` output is extended to the ~150 features, test fixture layout.

## Amendment 2026-10-20 (H's decisions, supersedes the items above where they conflict)

Found while planning: the champion was trained on `PAPER_DATA_PRODUCTS/csv/data_labels.csv`, which is
made by H's notebook `PAPER_DATA_PRODUCTS/Clean Data and Make Features.ipynb`
(`CleanDataAndMakeFeatures`), **not** by `scripts/make_lc_feature_rows.py`. The two differ.

- **Feature reference** = the notebook, after the changes below are made in r0b-retraining and the
  champion is retrained. Prod ports the notebook functions; parity is checked against the regenerated
  `data_labels.csv`.
- **Threshold flags** mean "ever above" (`lvra.utils.features.flux_threshold_features` semantics), not
  "latest point above". Notebook to be changed; analysis re-run.
- **Reliability cut** (R > 0.5) to be applied to `median_flux_*`, `max_flux` and `n_det_*`, plus a new
  feature counting detections below the cut. Changed in the notebook.
- **`rise_rate_{b}`**: as in the notebook (detections, `(last − first) / Δt` per band). Forced
  photometry is not needed; open item 2 is closed.
- **`delta_days_TOTAL`**: as in the notebook (latest − `discovery_mjd`, not an int).
- **`medianR_last5`**: NaN when fewer than 5 detections (as in the notebook).
- `band` is fed to the model as `pd.Categorical(categories=["u","g","r","i","z","y"])` (the champion
  uses `categorical_features="from_dtype"`).
- `json2cleandf` is not reused: it keeps only the latest source, while the features need the whole
  `diaSourcesList`. `flux_threshold_features` and `mag_to_njy_thresholds` are reused.
- "`distance`, `absMag`, `absMagMJD` fed as NaN" no longer applies (they are not notebook features).
- Classes: `gal` is merged into `real` at training, so the model outputs agn, bogus, extragal, mover, real.
