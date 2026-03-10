"""
Docstring for lvra.utils.features

Dev Notes on json2cleandf indexing fuckery
--------------------------------------------

The function json2cleandf takes a json file and generates a neat feature data frame. 
To do so it has to navigate the JSON data which contains:
- The lasair filter outputs in the first level. That is indexed by diaObjectId as per Lasair Schema.
- The latest diaSourceId data which is nested in ['alert']['diaSourcesList'] and is the last item 
of that list. That is indexed by diaSourceId as per Rubin Schema.

Here is the fun part: 
- Sometimes the same diaObjectId has multiple instances of data in the JSON file because several 
alerts arrived within the hour. Then the diaObjectId for our filter output data is not unique, 
and multiple latest diaSourceIds"point" to the same diaObjectId.
- Sometimes the alert column is NaN. So some diaObjectIds don't have that latest diaSourceId 
data at all. 

Today (2026-02-10), when looking at the output of my function I was getting these fun shapes:

> latestSourceIds_df.diaSourceId.unique().shape, latestSourceIds_df.diaObjectId.unique().shape
((41,), (40,))

> filterOutput_df.shape, filterOutput_df.diaObjectId.unique().shape
((82, 23), (40,))

In the latestSourceIds dataframe with have an extra source because I guess our alert batch 
there contained two separate source alerts for a given diaObject (as mentioned above)
then we have our filter output, which has more rows than unique objects... 
**This is weird and unexpected - do we have some repeats in the stream again?**

Even if the stream is working imporperly, I can't have my code fall apart because kafka is 
confused. So I needed to fix this.

The Goal: BE ABLE TO JOIN MY DATAFRAMES WITH A PROPER INDEX

The Solution: KEEP TRACK OF THE NUMBER OF MY LOOP USING loop_index. 
By incrementing it also when there is a failure due to a missing ['alert'] field, I make sure
that the index of my feature dataframes are NOT SEQUENTIAL BUT UNIQUE AND LINED UP properly. 

"""
import pandas as pd
from pathlib import Path
import numpy as np

mag_to_njy_thresholds = {'23': 2_291, 
                         '22': 5_754, 
                         '21': 14_454, 
                         '20': 36_309, 
                         '19': 91_201, 
                         '18': 229_086,
                         '17': 574_340,
                         }

def lc_features(df_lc, first_mjd, last_mjd, loop_index, R_THRESHOLD = 0.5):
    n_loR_sources = sum(df_lc.reliability<R_THRESHOLD)
    n_hiR_sources = sum(df_lc.reliability>R_THRESHOLD)
    medianR_last5 = np.nanmedian(df_lc.sort_values('midpointMjdTai', ascending=False).iloc[:5].reliability)
    GOOD_lc = df_lc[df_lc.reliability>R_THRESHOLD]

    ra_std = np.nanstd(GOOD_lc.ra)
    dec_std = np.nanstd(GOOD_lc.decl)
    
    delta_days_TOTAL = int(last_mjd - first_mjd)
    max_mjd, max_flux = GOOD_lc[GOOD_lc.psfFlux == GOOD_lc.psfFlux.max()][['midpointMjdTai', 'psfFlux']].values[0]
    delta_days_SINCE_MAX = int(last_mjd-max_mjd)
    delta_days_TO_MAX = int(max_mjd-first_mjd)

    n_gt22 = sum(GOOD_lc.psfFlux>mag_to_njy_thresholds['22'])
    n_gt21 = sum(GOOD_lc.psfFlux>mag_to_njy_thresholds['21'])
    n_gt20 = sum(GOOD_lc.psfFlux>mag_to_njy_thresholds['20'])
    n_gt19 = sum(GOOD_lc.psfFlux>mag_to_njy_thresholds['19'])
    n_gt18 = sum(GOOD_lc.psfFlux>mag_to_njy_thresholds['18'])

    first22 = np.isclose(GOOD_lc[GOOD_lc.psfFlux>mag_to_njy_thresholds['22']].midpointMjdTai.max(),
                         last_mjd )
    first21 = np.isclose(GOOD_lc[GOOD_lc.psfFlux>mag_to_njy_thresholds['21']].midpointMjdTai.max(),
                         last_mjd )
    first20 = np.isclose(GOOD_lc[GOOD_lc.psfFlux>mag_to_njy_thresholds['20']].midpointMjdTai.max(),
                         last_mjd )
    first19 = np.isclose(GOOD_lc[GOOD_lc.psfFlux>mag_to_njy_thresholds['19']].midpointMjdTai.max(),
                         last_mjd )
    first18 = np.isclose(GOOD_lc[GOOD_lc.psfFlux>mag_to_njy_thresholds['18']].midpointMjdTai.max(),
                         last_mjd )

    df = pd.DataFrame(np.atleast_2d([n_loR_sources,
                                     n_hiR_sources,
                                     medianR_last5,
                                     ra_std,
                                     dec_std,
                                     max_flux,
                                     delta_days_SINCE_MAX,
                                     delta_days_TO_MAX,
                                     delta_days_TOTAL,
                                     n_gt22,
                                     n_gt21,
                                     n_gt20,
                                     n_gt19,
                                     n_gt18,
                                     first22,
                                     first21,
                                     first20,
                                     first19,
                                     first18
                                    ]), 
                      columns=['n_loR_sources',
                               'n_hiR_sources',
                               'medianR_last5',
                               'ra_std',
                               'dec_std',
                               'max_flux',
                               'delta_days_SINCE_MAX',
                               'delta_days_TO_MAX',
                               'delta_days_TOTAL',
                               'n_gt22',
                               'n_gt21',
                               'n_gt20',
                               'n_gt19',
                               'n_gt18',
                               'first22',
                               'first21',
                               'first20',
                               'first19',
                               'first18'
                              ],
                      index=[loop_index])

    return df


def json2cleandf(path: Path):
    """Takes path to JSON data generated by the consumer and returns pandas dataframe containing the columns 
    in the Lasair filter that generated the JSON, plus the columns from the diaSource table (Rubin Schema) for 
    the latest diaSourceId. 

    This is a cleaning step before feature csv files can be created in the pyplines.

    Parameters
    ----------
    path: Path
        Path to the json file 

    Returns
    -------
    pd.DataFrame
    list
    """

    # 1. Load the whole JSON into a dataframe. 
    #    There are nested levels in the 'alert' column (which we will take care of)""
    #    'diaObject', 'diaSourcesList', 'diaForcedSourcesList', 'diaNondetectionLimitsList', 'annotations', 'ebv'
    json_df = pd.read_json(path)

    # 2. Make the latest_source_df 
    #    diaSourceList contains the diaSource table fields for each diaSource in a given diaObject/row
    #    the latest source is the last item. The easiest thing to do is extract the 1-row dataframe of the last source
    #    for each diaObjectId and collect them in a list to cocatenate at the end
    #    WARNING: CONCATENATION OF DATAFRAMES IN A LOOP IS SLOWER THAN THIS (because copies have to be made every time)

    latestSourceId_dfList = []
    objectIds_withoutAlert_col = []
    
    lc_features_dfList = []
    
    loop_index = 0
    
    for i in range(json_df.shape[0]):
        try: 
            latestSourceId_dfList.append(pd.DataFrame(json_df['alert'].values[i]['diaSourcesList'][-1], 
                                                index=[loop_index]))
            
            __lc = pd.DataFrame(json_df['alert'].values[i]['diaSourcesList'])
            __first_mjd = json_df.iloc[i].firstDiaSourceMjdTai
            __last_mjd = json_df.iloc[i].lastDiaSourceMjdTai
    
            lc_features_dfList.append(lc_features(__lc, 
                                                  first_mjd=__first_mjd, 
                                                  last_mjd=__last_mjd, 
                                                  loop_index=i, 
                                                  R_THRESHOLD = 0.5
                                                 )
                                     )
            
            loop_index += 1
        except TypeError:
            loop_index += 1 # YES THIS IS CORRECT DO NOT REMOVE - see dev notes for explanation
            # this happens if the alert column for that row is NaN
            # if that happens, we have a problem and we need to log it
            objectIds_withoutAlert_col.append(json_df['diaObjectId'].values[i])

    # 3. Concatenate the source ID and LC feature dataframes
    latestSourceIds_df = pd.concat(latestSourceId_dfList)
    latestSourceIds_df.diaSourceId = latestSourceIds_df.diaSourceId.astype(str)
    latestSourceIds_df.diaObjectId = latestSourceIds_df.diaObjectId.astype(str)

    lc_features_df = pd.concat(lc_features_dfList)


    # 4. Make the filter output df
    #    Take all rows (axis=0), and every column (axis=1) except the last one ('alert')
    filterOutput_df = json_df.iloc[:,:-1]
    filterOutput_df.diaObjectId = filterOutput_df.diaObjectId.astype(str)

    # 5. Join the data frames!
    clean_df = filterOutput_df.join(latestSourceIds_df, rsuffix='_sourceId').join(lc_features_df, rsuffix='_lcfeats')

    # If there were missing alert fields some latestSourceId and lc_features columns will be NaN
    # here we remove them
    clean_df = clean_df[~clean_df.diaObjectId_sourceId.isna()]

    # 5.5 CHECK THAT I DIDN'T FUCK UP INDEXES
    if sum(~(clean_df.diaObjectId == clean_df.diaObjectId_sourceId)) > 0:
        raise ValueError("The diaObjectId from the filter output and the diaObjectId from the latest diaSourceId do not match for some rows. This should never happen, check your code.")



    return clean_df.reset_index(drop=True), objectIds_withoutAlert_col