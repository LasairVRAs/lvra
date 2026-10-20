# Light Curve Features Functions
# Written by CLaude based on Heloise's code.Reviewed by Heloise
# Oversight Level: High. 
# Accountable: Heloise.

import numpy as np
import pandas as pd

from lvra.utils.features import mag_to_njy_thresholds

BANDS = ["u", "g", "r", "i", "z", "y"]

# The Reliability threshold is set today 2026-10-20 
# at 0.5 because it is what I use in the lvra-fodder filter 
# which creates the input stream of the LVRA.
# Here it separates the "low" and "high" R detections
# Of course R =0.5 is still pretty naff, but it makes sense to set it this way
# because when we calculate e.g. the number of detections brighter than 22nd mag
# and only count the high R detections, we effectively say "How many detections
# brighter than XX would have already been seen in our stream?"
R_THRESHOLD = 0.5

# Honestly can't remember why I picked 10. Might be vibes, might be a histogram. 
SNR_THRESHOLD = 10

THRESHOLD_MAGS = ["18", "19", "20", "21", "22", "23"]


def brighter_than_features(lc_hiR: pd.DataFrame, mag: str) -> dict:
    """Calculates the following flags:
    - ever_brighter_XX: HAs the transient ever been brighter than XX mag
    - N_brighter_XX: How many detections are brighter than XX. Note that this function does not enforce
    that the detections have high R. In the pipeline we provide only the high R lightcurve to this function. 
    - first_brighter_XX: is this the first time it's been brighter than XX

    where XX is a threshold mag that I have in my "mag to nanojansky dictionary":
    - ["18", "19", "20", "21", "22", "23"]

    Parameters
    -----------
    lc_hiR: pd.DataFrame
       The lightcurve of our object. We want only high R detections but this is not enforced in this function. 
       The dataframe MUST contain a .psfflux column.
    mag: str
       The magnitude value we are interested in. We ask for string because it's a key in a dictionary. 

    Return
    ------
    dictionary of 3 items

    Raises
    -------
    Nothing. 
    """

    thr = mag_to_njy_thresholds[mag]
    n_brighter = int((lc_hiR.psfflux > thr).sum())

    return {
        f"ever_brighter_{mag}": int(n_brighter > 0),
        f"N_brighter_{mag}": n_brighter,
        f"first_brighter_{mag}": int(n_brighter == 1 and lc_hiR.psfflux.iloc[-1] > thr),
    }


def reliability_features(lc: pd.DataFrame) -> dict:
    """Calculates the features related to the reliability score:
    - n_hiR_sources: Number of rows where the score is greater than the threshold defined at the top of this module
    - n_loR_sources: Number of rows where the score is lower 
    - medianR_last5: Median of the last 5 rows. If not 5 rows: nan
    - medianR: The median

    Parameters
    -----------
    lc : pd.DataFrame
       The lightcurve. **It should be the lightcurve corresponding to one single diaObjectId** otherwise it's meaningless.
       This is not enforced in the function. 

    Returns
    --------
    dictionary of 4 items

    Raises
    ------
    Nothing. 
    
    """
    r = lc.reliability
    return {
        "n_hiR_sources": int((r > R_THRESHOLD).sum()),
        "n_loR_sources": int((r < R_THRESHOLD).sum()),
        "medianR_last5": np.nanmedian(r.iloc[-5:]) if len(r) >= 5 else np.nan,
        "medianR": np.nanmedian(r),
    }


def max_flux_features(lc_hiR: pd.DataFrame, discovery_mjd: float) -> dict:
    """Features related to the maximum flux:
    - max_flux: The value of max flux in nano janskies
    - delta_days_since_max: The number of days since the maximum. 0 if today is the max
    - delta_days_to_max: Number of days between with firstDiaSourceMJDTai and the MJD at max

    MJD at max is not returned as it is not a feature.

    Parameters
    -----------
    lc_hiR: pd.DataFrame
       the lightcurve. MUST contain .psfflux and .midpointmjdtai. We expect the lightcurve
       data frame contains only the detections with high R. That is not enforced though.

    Returns
    --------
    dictionary of 3 items
    """
    i_max = lc_hiR.psfflux.argmax()
    mjd_max = lc_hiR.midpointmjdtai.iloc[i_max]
    return {
        "max_flux": lc_hiR.psfflux.iloc[i_max],
        "delta_days_since_max": lc_hiR.midpointmjdtai.iloc[-1] - mjd_max,
        "delta_days_to_max": mjd_max - discovery_mjd,
    }


def snr_features(lc: pd.DataFrame) -> dict:
    """SNR related features, regardless of R value:
    - n_det_snr10_allbands: Number of detections (all R values and bands) with SNR >10
    - median_snr_allbands: Median SNR (all bands and R values)
    - current_snr: Current SNR

    Parameters
    -----------
    lc : pd.DataFrame
       The lightcurve. **It should be the lightcurve corresponding to one single diaObjectId** otherwise it's meaningless.
       This is not enforced in the function. 

    Returns
    -------
    dictionary of 3 items

    Raises
    -------
    Nothing
    """
    return {
        "n_det_snr10_allbands": int((lc.snr > SNR_THRESHOLD).sum()),
        "median_snr_allbands": np.nanmedian(lc.snr),
        "current_snr": lc.snr.iloc[-1],
    }


def band_features(lc_hiR: pd.DataFrame, band: str) -> dict:
    """
    Lightcurve features by filters (bands):
    - median_flux_{band}
    - n_det_{band}
    - n_det_snr10_{band}
    - rise_rate_{band}: just the linear gradient (delta_flux/delta_mjd)

    Note
    -----
    On the pipeline we ONLY use R>0.5 lightcurve points to calculate these

    Parameters
    ----------
    lc_hiR: pd.DataFrame
       the lightcurve. MUST contain .psfflux and .midpointmjdtai. We expect the lightcurve
       data frame contains only the detections with high R. That is not enforced though.

    band: str
       u, g, r, i, z, y 
    
    Raises
    ------
    Nothing. 

    Return 
    -------
    Dictionary of 4 items
    """

    # Lightcurve in the right band
    lc_b = lc_hiR[lc_hiR.band == band]
    # the keys of our dictionary, with the right band in the key 
    keys = [f"median_flux_{band}", f"n_det_{band}", f"n_det_snr10_{band}", f"rise_rate_{band}"]

    # return NaN for each key if we don't have that band in our data
    if lc_b.empty:
        return dict.fromkeys(keys, np.nan)

    # Delta t. 
    dt = lc_b.midpointmjdtai.iloc[-1] - lc_b.midpointmjdtai.iloc[0]
    # rise rate is delta flux /delta t, unless delta t is 0, then rise_rate is nan
    rise_rate = (lc_b.psfflux.iloc[-1] - lc_b.psfflux.iloc[0]) / dt if dt != 0 else np.nan

    return dict(zip(keys, [
        np.median(lc_b.psfflux),
        len(lc_b),
        int((lc_b.snr > SNR_THRESHOLD).sum()),
        rise_rate,
    ]))


def lc_features(lc: pd.DataFrame, discovery_mjd: float) -> dict:
    """
    Puts together all the LC features by calling the functions we have defined
    in this module but also calculating other generic features that are one liners and 
    don't need their own functions. 

    Also creats the lc_hiR dataframe which only includes the detections with high R,
    which is passed to some of our functions where we want to ensure the features are calculated
    only on high R detections. The R threshold is defined in the module and NOT a parameter
    that can be easily changed (by choice).

    Parameters
    -----------
    lc : pd.DataFrame
       The lightcurve. **It should be the lightcurve corresponding to one single diaObjectId** otherwise it's meaningless.
       This is not enforced in the function. 

    discovery_mjd: float
       the firstDiaSourceMJDTai field we get from the Lasair filter

    Returns
    -------
    Dictionary of the features
    """

    lc_hiR = lc[lc.reliability > R_THRESHOLD]
    feats = {}
    for mag in THRESHOLD_MAGS:
        feats.update(brighter_than_features(lc_hiR, mag))
    feats.update(reliability_features(lc))
    feats["ra_std"] = np.std(lc.ra)
    feats["dec_std"] = np.std(lc.decl)
    feats.update(max_flux_features(lc_hiR, discovery_mjd))
    feats["delta_days_TOTAL"] = lc_hiR.midpointmjdtai.iloc[-1] - discovery_mjd
    feats["median_extendedness"] = np.nanmedian(lc_hiR.extendedness)
    feats.update(snr_features(lc))
    feats["median_flux_allbands"] = np.nanmedian(lc_hiR.psfflux)
    for band in BANDS:
        feats.update(band_features(lc_hiR, band))
    return feats
