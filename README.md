# Lasair VRA



---
# Change History

**2025-12-04**: First features from the alerts (+ start of science notes)
* [PR 11](https://github.com/HeloiseS/lvra/pull/11)

**2025-11-13:** 
* Added CI (unitest and linter)
* The `public_settings.yaml` can now be provided by andd environment variable `LVRA_SETTINGS` + made a `public_settings_ci.yaml` for the CI.  

**2025-11-12:** 
* The `kafka_consumer.py` now saves one json file for all the alerts in one polling batch
under the name `YYYY-MM-DD_HH-MM-SS.json`. This file is set up to start with `[` and end with `]` such that it can be placed into a pandas dataframe using `pd.read_json('YYYY-MM-DD_HH-MM-SS.json')`
