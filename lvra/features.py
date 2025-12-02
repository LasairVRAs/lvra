import pandas as pd
from pathlib import Path

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
    def __init__(self):
        super().__init__()