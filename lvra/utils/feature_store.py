"""
Utility functions to handle connection and transactions with the Features sqlite database

Oversight: High
Accountable: Heloise

Written by Claude and Reviewed and commented by Heloise on 2026-10-21

Review Notes
-------------
Wondered whether to create and object (e.g. FeaturStore) as all the functions
here pass the connection around. In the end won't do it because the connection is
the only thing being passed around in these functions; no other state or 
data is shared so it adds a layer without adding functionality. 


Removed `con.executescript(schema_path.read_text(encoding="utf-8"))` in `connect()`
and updated the .connect() step to raise an error if the database doesn't exist.

On WAL mode and not locking the db. I thought this was superfluous because
I have lock file mechansisms in bigbashboy, however these are stage specific, so i cna't have 
two annotators runnign concurently for example, but I very well could have an annotator from 
a previous cycle running whilst the feature maker of the next cycle is starting. WAL mode 
ensures my feature maker can write to the table whilst allowing the annotator to read what's
already been done. 

NOTE: WAL only allows one writer at a time. The write transactions are pretty small so 
we should be fine to wait. 

My current pipeline can't result in deadlocks because it's not circular, it's linear. 
I'm happy with this for now, although the lenght of the cycles may need to be refined as 
more alerts come through.
"""

import sqlite3
from pathlib import Path

import pandas as pd

from lvra.utils.alert_rows import FEATURE_NAMES
from lvra.utils.exceptions import LVRAValueError


SCORE_CLASSES = ["extragal", "mover", "real", "bogus", "agn", "gal"]
MODEL_ROLES = ['champion', 'challenger', 'retired']

def connect(db_path: Path) -> sqlite3.Connection:
    """Create our connection to the features data base
    
    Parameters
    -----------
    db_path: Path
       Path to the features.db

    Return
    ------
    sqlite3.Connection

    Raises
    ------
    sqlite3.OperationalError (if the databse file is missing)
    """
    # A long winded version of con = sqlite3.connect(db_path)
    # which ensures the code raises an error if my data base doesn't exist
    con = sqlite3.connect(f"file:{db_path}?mode=rw", uri=True)

    # WAL allows reads whilst the file is handling a "write" transaction
    # The writes happen in a side file (features.db-wal) so as not to lock the
    # features.db file that the reads will happen on. 
    # If we have a lot of alerts coming we might have a case where the feature_makre is writing
    # whilst the predictor or annotator from the previous cycle is reading. 
    con.execute("PRAGMA journal_mode = WAL")

    # By default sqlite doesn't care about foreig keys. Here we're asking to care
    # this matters for diaSourceId in model_scores which is a reference to the diaSourceId
    # that is the priamry key of the features table. 
    # Basically a score for an alert with no features gets rejected. It should NEVER happen
    # we use database normalisation to ensure it doesn't. 
    con.execute("PRAGMA foreign_keys = ON")

    return con


def _insert_or_ignore(con, table, df, cols):
    """Utility to all our insert functions below. If a primary key is already present
    we IGNORE the row. (Opposite of an UPSERT if you will)
    
    Parameters
    ----------
    con: sqlite3.Connection
       Our connection to features.db
    table: str
       Name of the table in our databse. 
    df: pd.DataFrame
       Pandas dataframe containing our data that we want to put in our database
    cols: str or list[str]
       The columns we want to select in our data frame and put in our database

    Note
    -----
    This assumes you've named your columns THE SAME in the database and the dataframe
    
    Returns
    -------
    Number of rows inserted
    """

    # Creates an iterator (.itertuples) that provides one tuple per row of our df
    # when .executesmany() runs, the iterator triggers and one INSERT per row is done
    # .astype(object).where(df[cols].notna(), None) turns all the types of the non null columns
    # into raw Python ones as np,int64 (for example) are rejected by sqlite. The NaN are turned to None
    # which SQLite stores as NULL. 
    values = df[cols].astype(object).where(df[cols].notna(), None).itertuples(index=False)

    # Fancy dynamic way to write the correct query for any number of columns
    # with the col names separated by , and the values also separated by , 
    # If the primary key already exists we don't insert. (It's NOT AN UPSERT)
    sql = f"INSERT OR IGNORE INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"

    # con.total_changes is a running count of the rows changed since the connection opened
    # we record what that number is BEFORE we execute our inserts
    before = con.total_changes
    with con:
        con.executemany(sql, values)
    # At the end we subtract the new count from the old count to get the number of changes. 
    return con.total_changes - before


def insert_features(con, rows_df: pd.DataFrame, stem: str) -> int:
    """Insert the features we calculated in our feature store table

    Parameters
    ----------
    con: sqlite3.Connection
       Our connection to features.db
    rows_df: pd.DataFrame
       The table of features we've just created
    stem: str
       The stem for this cycle of ingest
    """

    # FEATURE_NAMES imported. It is created from the lvra_features.csv in /data
    cols = ["diaSourceId", "diaObjectId", "stem"] + FEATURE_NAMES
    return _insert_or_ignore(con, "features", rows_df.assign(stem=stem), cols)


def read_features(con, stems: list[str]) -> pd.DataFrame:
    """Reads features for all the objects in a list of stems

    Parameters
    ----------
    con: sqlite3.Connection
       Our connection to features.db  
    stems: list[str]
       List of strings containing the stems to be processed. 

    Return
    -------
    pd.DataFrame (the features)
    """

    # Remember your queries have ?,?,?... placeholders
    sql = f"SELECT * FROM features WHERE stem IN ({', '.join('?' * len(stems))})"
    # they are replaced by the stems in the function that sends the query, 
    # here we can us pandas directly to retrieve the data as a dataframe automatically
    return pd.read_sql_query(sql, con, params=stems)


def insert_scores(con, scores_df: pd.DataFrame, stem: str, role: str, version: str) -> int:
    """Inserts the scores into the model_scores table of features.db 

    Parameters
    ----------
    con: sqlite3.Connection
       Our connection to features.db  
    scores_df: pd.DataFrame
       The scores dataframe 
    stem: str
       The stem that is being processed
    role: str
       A valid role: champion, challenger, retired. This is enforced.

    Raises
    ------
    LVRAValueError
    """
    if role not in MODEL_ROLES:
        raise LVRAValueError(f"Invalid Role. Chose from {MODEL_ROLES}. ")
    
    cols = ["diaSourceId", "diaObjectId", "stem", "model_role", "model_version"] + SCORE_CLASSES

    # The re-index here is to ensure the columns of the dataframe match that of our table
    # since when I trained I absorbed the "gal" class into "real" we don't have a "gal" score or column
    # This adds this back in (of course the column will have NULL values)
    df = scores_df.reindex(columns=["diaSourceId", "diaObjectId"] + SCORE_CLASSES)

    return _insert_or_ignore(con, "model_scores", df.assign(stem=stem, model_role=role, model_version=version), cols)
