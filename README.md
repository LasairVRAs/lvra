# Lasair VRA



---
# Change History

**2025-11-12:** The `kafka_consumer.py` now saves one json file for all the alerts in one polling batch
under the name `YYYY-MM-DD_HH-MM-SS.json`. This file is set up to start with `[` and end with `]` such that it can be placed into a pandas dataframe using `pd.read_json('YYYY-MM-DD_HH-MM-SS.json')`
