import pandas as pd
from pathlib import Path
from lasair import LasairError, lasair_client as lclient
import os

endpoint = "https://lasair-lsst-dev.lsst.ac.uk/api"
token = os.getenv('LASAIR_LSST_TOKEN')


subfields_diasource = ['diaObjectId',
    'apFlux_flag',
    'apFlux_flag_apertureTruncated',
    'centroid_flag',
    'dipoleChi2',
    'dipoleFluxDiff',
    'dipoleMeanFlux',
    'extendedness',
    'forced_PsfFlux_flag',
    'forced_PsfFlux_flag_edge',
    'glint_trail',
    'isDipole',
    'isNegative',
    'pixelFlags',
    'pixelFlags_bad',
    'pixelFlags_cr',
    'pixelFlags_crCenter',
    'pixelFlags_edge',
    'pixelFlags_streakCenter',
    'psfChi2',
    'psfFlux_flag',
    'psfFlux_flag_edge',
    'psfFlux_flag_noGoodPixels',
    'snr',
    'trail_flag_edge',
    'bboxSize',
    'dipoleFitAttempted',
]

def diasource_api_call(diaObjectId_list, subset_fields=None):
    """
    """
    # TODO: finsih when my API request limit has increased
    L = lclient(token, endpoint=endpoint)
    diasource_list_series = []
    for _id in diaObjectId_list:
        _res = L.object(_id, lite=False)
        diasource_list_series.append(pd.Series(_res['diaSourcesList'][0]))
    
    df = pd.DataFrame(diasource_list_series)
    if subset_fields is not None:
        df = df[subset_fields]
    return df



class Features(object):
    """Parent feature class with the class methods to load data
    """
    columns = []
    @classmethod
    def _check_path_exists(cls, path):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"{p} does not exist")
        return p
    
    @classmethod
    def from_json(cls, path, subset_columns=None):
        """User facing constructor that makes the features from a single json file"""
        p = cls._check_path_exists(path)
        raw = pd.read_json(p)
        return cls.extract_features(raw, subset_columns=subset_columns)
    
    @classmethod
    def from_csv(cls, path, subset_columns=None):
        """User facing constructor that makes the features from a single csv file"""
        p = cls._check_path_exists(path)
        raw = pd.read_csv(p)
        return cls.extract_features(raw, subset_columns=subset_columns)
    
    @classmethod
    def from_dataframe(cls, df, subset_columns=None):
        """User facing constructor that makes the features from a dataframe"""
        return cls.extract_features(df, subset_columns=subset_columns)

    @classmethod
    def extract_features(cls, raw, subset_columns=None):
        """Extract features of interest from raw dataframe obtained from kafka json"""
        df = raw.copy()
        if subset_columns is None:
            subset_columns = cls.columns

        # Will need to catch exceptions when not all subset columns are present
        # in the raw dataframe
        features = df[subset_columns]
        return features


class FeaturesRealBogus(Features):
    """Class to make the features needed for real-bogus classification"""

    columns = ['diaObjectId', 'latestR', 'nDiaSources', 'ebv',
       'ra', 'decl', 'separationArcsec', 'direct_distance', 'distance', 'z', 'photoZ',
       'photoZErr', 'physical_separation_kpc','raErr', 'decErr', 'ra_dec_Cov']
    
    @classmethod
    def add_diasource_features(cls, df, subset_fields=subfields_diasource):
        # 1. extract unique diaObjectIds
        ids = df['diaObjectId'].dropna().unique()

        # 2. call your API function
        dias_df = diasource_api_call(ids, subset_fields=subset_fields)

        # 3. join back onto the original df
        # dias_df must have 'diaObjectId' as a column or index
        if 'diaObjectId' not in dias_df.columns:
            dias_df['diaObjectId'] = ids

        enriched = df.merge(dias_df, on='diaObjectId', how='left')
        return enriched
    
    def __init__(self):
        super().__init__()


