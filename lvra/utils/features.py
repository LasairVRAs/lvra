import pandas as pd
from pathlib import Path
from lasair import lasair_client as lclient
import os

endpoint = "https://lasair-lsst-dev.lsst.ac.uk/api"
token = os.getenv('LASAIR_LSST_TOKEN')


subfields_diasource = ['diaObjectId',
                       'diaSourceId',
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

def diasource_api_call(diaObjectId_list: list, 
                       subset_fields:list = None
                       ) -> pd.DataFrame:
    """
    Call Lasair API to gather the most recent diaSource fields for a list of diaObjectIds
    
    Parameters
    ----------
    diaObjectId_list : list
        List of diaObjectIds to query
    subset_fields : list, optional
        List of diaSource fields to return. If None, returns the subset defined in the module.
    """

    L = lclient(token, endpoint=endpoint)
    diasource_list_series = []
    for _id in diaObjectId_list:
        _res = L.object(_id, lite=False)
        # get the most recent diaSource fields and append to our list of Series
        # NOTE: I hope the first item is ALWAYS the most recent!


        diasource_list_series.append(pd.Series(_res['diaSourcesList'][0]))
    
    df = pd.DataFrame(diasource_list_series)
    if subset_fields is not None:
        df = df[subset_fields]

    return df



class Features(object):
    """Parent feature class with the class methods to load data
    The features of interest will be defined in the children classes
    as class attributes. 

    Methods
    -------
    from_json(path, subset_columns=None)
        Load features from a JSON file
    from_csv(path, subset_columns=None)
        Load features from a CSV file
    from_dataframe(df, subset_columns=None)
        Load features from a pandas DataFrame
    extract_features(raw, subset_columns=None)
        Extract features of interest from raw dataframe

    Raises
    ------
    FileNotFoundError
    """
    columns = []
    @classmethod
    def _check_path_exists(cls, path):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"{p} does not exist")
        return p
    
    @classmethod
    def from_json(cls, 
                  path: str, 
                  subset_columns: list = None) -> pd.DataFrame:
        """Reads features from a single json file into a dataframe
        
        Parameters
        ----------
        path : str
            Path to the json file
        subset_columns : list, optional
            List of columns to extract. If None, extracts the class defined columns.
        """
        p = cls._check_path_exists(path)
        raw = pd.read_json(p)
        return cls.extract_features(raw, subset_columns=subset_columns)
    
    @classmethod
    def from_csv(cls,
                 path: str, 
                 subset_columns: list = None) -> pd.DataFrame:
        """Reads features from a single csv file into a dataframe
               
        Parameters
        ----------
        path : str
            Path to the json file
        subset_columns : list, optional
            List of columns to extract. If None, extracts the class defined columns.
        """
        p = cls._check_path_exists(path)
        raw = pd.read_csv(p)
        return cls.extract_features(raw, subset_columns=subset_columns)
    
    @classmethod
    def from_dataframe(cls, 
                       df: pd.DataFrame, 
                       subset_columns: list = None) -> pd.DataFrame:
        """Reads features from a dataframe
               
        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing the raw features
        subset_columns : list, optional
            List of columns to extract. If None, extracts the class defined columns.
        """
        return cls.extract_features(df, subset_columns=subset_columns)

    @classmethod
    def extract_features(cls, 
                         raw: pd.DataFrame,
                         subset_columns: list = None) -> pd.DataFrame:
        """Extract features of interest from raw dataframe obtained from kafka json
        
        Parameters
        ----------
        raw : pd.DataFrame
            The raw dataframe from the kafka stream
        subset_columns : list, optional
            List of columns to extract. If None, extracts the class defined columns.
        """
        df = raw.copy()
        if subset_columns is None:
            subset_columns = cls.columns

        # Will need to catch exceptions when not all subset columns are present
        # in the raw dataframe
        # features = df[subset_columns]
        features = df 
        return features


class FeaturesRealBogus(Features):
    """Class to make the features needed for real-bogus classification
    
    Methods
    -------
    add_diasource_features(df, subset_fields=subfields_diasource)
        Takes the features dataframe and adds diaSource features by calling Lasair API
    """

    columns = ['diaObjectId', 'latestR', 'nDiaSources', 'ebv',
       'ra', 'decl', 'separationArcsec', 'direct_distance', 'distance', 'z', 'photoZ',
       'photoZErr', 'physical_separation_kpc','raErr', 'decErr', 'ra_dec_Cov']
    
    @classmethod
    def add_diasource_features(cls, 
                               df: pd.DataFrame, 
                               subset_fields: list = subfields_diasource
                               ) -> pd.DataFrame:
        """Takes the features dataframe and adds diaSource features by calling Lasair API
        
        Parameters
        ----------
        df : pd.DataFrame
            DataFrame containing the features. MUST CONTAIN 'diaObjectId' column.
        subset_fields : list, optional
            List of diaSource fields to return. If None, returns the subset defined in the module.
        
        Returns
        -------
        pd.DataFrame
            DataFrame with the added diaSource features

        Raises
        ------
        KeyError
            If 'diaObjectId' column is not present in the input dataframe
        """
        # 1. extract unique diaObjectIds
        try:
            ids = df['diaObjectId'].dropna().unique()
        except KeyError:
            raise KeyError("Input dataframe must contain 'diaObjectId' column to add diaSource features.")

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


