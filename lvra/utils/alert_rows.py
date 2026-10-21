"""
Making feature rows for each alerts in our JSON file from our Kafka stream

Oversight: High. 
Accountable: Heloise.

Written by Claude based on specs written with Heloise. Reviewed and commented by Heloise
"""

import json
from pathlib import Path

import pandas as pd

from lvra.utils.lc_features import lc_features


FEATURE_NAMES = pd.read_csv(Path(__file__).resolve().parents[2] / "data" / "lvra_features.csv").feature.tolist()

# Mapping of the field names form what we get in the filter to how I called them in the
# training data frames. Matters because I trained with named columns
FILTER_TO_TRAINING = {
    "z": "sherlock_z",
    "photoZ": "sherlock_photoz",
    "photoZErr": "sherlock_photozerr",
    "separationArcsec": "sherlock_separation_arcsec",
    "physical_separation_kpc": "sherlock_separation_kpc",
    "sherlock_classifications": "sherlock_classification",
    "decl": "dec",
    "ra": "ra",
    "ebv": "ebv",
    "direct_distance": "direct_distance",
    "best_distance": "best_distance",
    "best_distance_flag": "best_distance_flag",
}


def entry_to_row(entry: dict) -> dict:
    """Takes an Alert entry (an alert dictionary in our JSON from tje kafka stream)
    and returns a row of features
    
    Parameters
    ---------
    entry: dict
        One alert is a nested dictionary. Here the entry must contain the ["alert"] sub dictoinary
        which is only the case if our Lasair filter is set to "full", which is the case for lvra-fodder
    
    Returns
    --------
    dictionary 
    """

    #The sources are lightcurve points. 
    sources = entry["alert"]["diaSourcesList"]

    #Trigger is the item (entr) in diaSourcesList that has the latest midpointmjdTai. 
    # It's the latest data point for this lightcurve, it contains information specific to the source
    # such as the dipole flags, iyy, etc.. all that stuff. 
    trigger = max(sources, key=lambda s: s["midpointMjdTai"])

    # Creates ordered lightcurve (should be order already but you never know)
    lc = pd.DataFrame(sources).rename(columns=str.lower).sort_values("midpointmjdtai").reset_index(drop=True)

    row = {"diaObjectId": entry["diaObjectId"], "diaSourceId": trigger["diaSourceId"]}

    # All the alert source specific things like the dipole flags, etc...
    row.update({k.lower(): v for k, v in trigger.items()})

    # grabs z photoZ, photoZErr, separation, direct distnace, ra, decl, ebv, separation kpc, sherlock classification
    row.update({new: entry[old] for old, new in FILTER_TO_TRAINING.items()})

    # Adds the lightcurve features to our dictionary. 
    row.update(lc_features(lc, entry["firstDiaSourceMjdTai"]))
    return row


def json_to_feature_rows(path: Path) -> tuple[pd.DataFrame, list[int]]:
    """Takes JSON file and makes features for each object in our JSON  of alerts
    
    Parameters
    -----------
    path: Path
       Path to a JSON file

    Returns
    --------
    pd.Dataframe: the features
    list[int]: which diaObjectId didn't have the "alert" field. If any. (Used to happen during commissioning
    might be obsolete now)
    """

    # load json, each entry (dictoinaries at top level) is an Alert. 
    with open(path) as f:
        entries = json.load(f)

    rows, no_alert = [], []

    for entry in entries:
        # note the "alert" field is the full Rubin alert nested into the Lasair alert
        # there are two usage of the term alert which is confusing. A lasair alert
        # won't have the "alert" field if it's only asked to produce streams with the standard
        # kafka stream mode, rather than e.g. full where, in addition to the Lasair filter fields 
        # we also get the full Rubin alert (except the images)
        if entry.get("alert") is None:
            no_alert.append(entry["diaObjectId"])
            continue
        rows.append(entry_to_row(entry))

    return pd.DataFrame(rows, columns=["diaObjectId", "diaSourceId"] + FEATURE_NAMES), no_alert
