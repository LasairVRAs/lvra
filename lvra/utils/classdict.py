"""Utiltiy to create the _class_dict for the Lasair Annotations
Oversight: High
Accountable: Heloise

Written by Claude, reviewed and commented by Heloise

"""
import numpy as np
import pandas as pd

from lvra.utils.feature_store import MODEL_ROLES


THRESHOLDS = range(18, 24) # the magnitude threhsolds for which I create flags.
BANDS = "ugrizy"

# Mapping between the public names and the column names in my data. 
# in later versions I could just fix the sodding column names
PUBLIC_FEATURES = {
    **{f"n_gt{t}": f"N_brighter_{t}" for t in THRESHOLDS},
    **{f"everbrighter{t}": f"ever_brighter_{t}" for t in THRESHOLDS},
    **{f"first{t}": f"first_brighter_{t}" for t in THRESHOLDS},
    "n_loR_sources": "n_loR_sources",
    "n_hiR_sources": "n_hiR_sources",
    "max_flux": "max_flux",
    "delta_days_since_max": "delta_days_since_max",
    "delta_days_to_max": "delta_days_to_max",
    "delta_days_total": "delta_days_TOTAL",
    "current_snr": "current_snr",
    **{f"n_det_{b}": f"n_det_{b}" for b in BANDS},
    **{f"n_det_snr10_{b}": f"n_det_snr10_{b}" for b in BANDS},
}


def format_classification(p: float) -> str:
    """We "round" to 6 decimal places our classification field. It's enough for ranking and easier on the user's eyes"""
    return f"{p:.6f}"


def _clean(x):
    """CLean up the types and reducs the number of sig figs we quote for scores to save characters.
    (max 4096 allowed in a Lasair annotator)
    """
    # If we have a field that is None or NaN this will be True and we can unify and return None
    if pd.isna(x):
        return None
    # if it's a string, you can go as you are
    if isinstance(x, str):
        return x
    # if you are a boolean or numpy.bool_ you must be a bool
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    
    # finally if you're not non a string or a bool you're probably a number:
    # we ensure that you only have 6 sig figs and are still a float. We 
    # do the float to string to float to avoid getting scientific notation stuff. 
    v = float(f"{x:.6g}")
    return int(v) if v.is_integer() else v # if you;re an integer you go as an integer, othweise, .6g. 


def build_classdict(features: dict, slots: dict) -> dict:
    # always add our blame_diaSourceId
    d = {"blame_diaSourceId": int(features["diaSourceId"])}

    # loop through the available roles. at time of writing: Champion, Challenger, Retired
    for role in MODEL_ROLES:
        slot = slots.get(role) # get the dictionary of scores for that role
        # build the dictionary that corresponds to that role if exists in our slots, otherwise make it None
        # the dict comprehension creates our version, extragal, bogus, agn, etc... score key-pair values
        # the _clean() function ensures the right type and level of rounding
        d[role] = None if slot is None else {k: _clean(v) for k, v in slot.items() if _clean(v) is not None}

    # add ALL of our extra public features
    d.update({name: _clean(features[col]) for name, col in PUBLIC_FEATURES.items()})
    return d
