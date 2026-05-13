CREATE TABLE IF NOT EXISTS feature_making (
    stem TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT current_timestamp,
    r0b INTEGER
);

CREATE TABLE IF NOT EXISTS annotating (
    stem TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT current_timestamp,
    r0b INTEGER
);

CREATE TABLE IF NOT EXISTS predict (
    stem TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT current_timestamp,
    r0b INTEGER
);

CREATE TABLE IF NOT EXISTS diaobjid_stems (
    diaObjectId INTEGER PRIMARY KEY,
    stem TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS provenance (
    ID INTEGER PRIMARY KEY,
    diaObjectId INTEGER,
    diaSourceId INTEGER,
    stem TEXT,
    score REAL,
    model_name TEXT,
    model_version TEXT,
    timestamp TEXT NOT NULL DEFAULT current_timestamp
);

CREATE TABLE IF NOT EXISTS threshold_flags_provenance(
    ID INTEGER PRIMARY KEY,
    diaObjectId INTEGER,
    diaSourceId INTEGER,
    stem TEXT,
    n_gt22 INTEGER,
    n_gt21 INTEGER,
    n_gt20 INTEGER,
    n_gt19 INTEGER,
    n_gt18 INTEGER,
    brighter22 INTEGER,
    brighter21 INTEGER,
    brighter20 INTEGER,
    brighter19 INTEGER,
    brighter18 INTEGER,
    first22 INTEGER,
    first21 INTEGER,
    first20 INTEGER,
    first19 INTEGER,
    first18 INTEGER,
    timestamp TEXT NOT NULL DEFAULT current_timestamp
);
