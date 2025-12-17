import pandas as pd
import numpy as np

def nsr_sampling(predictions_df: pd.DataFrame,
                 score_column: str = 'pred',
                 Ntop: int = 5,
                 Nmid: int = 10,
                 mid_bracket: tuple = (0.4, 0.6),
                 ) -> list:
    """Not So-Random Sampling (NSR Sampling)

    With default values, selects the top 5 (Ntop) scoring samples and 10 (Nmid) random samples
    from a bracket (0.4,0.6) ofmid-range scores.
    
    Parameters
    ----------
    predictions_df : pd.DataFrame
        DataFrame with at lease the `diaSourceId` and score columns.
    score_column : str
        Name of the column containing the prediction scores.
    Ntop : int
        Number of top scoring samples to select.
    Nmid : int
        Number of mid-range scoring samples to randomly select.
    mid_bracket : tuple
        Score range for mid-range sampling (inclusive).

    Returns
    -------
    list
        List of selected `diaSourceId`s.
    """
    sorted_predictions = predictions_df.sort_values(score_column, ascending=False)
    topN = sorted_predictions.iloc[:Ntop].diaSourceId.values
    try:
        midN = sorted_predictions[(sorted_predictions[score_column]>mid_bracket[0]) 
                    & (sorted_predictions[score_column]<mid_bracket[1])].sample(Nmid).diaSourceId.values
    except ValueError:
        midN = sorted_predictions.iloc[Ntop:].diaSourceId.sample(Nmid).values
        print(f"Warning: Not enough samples in mid_bracket {mid_bracket}, sampling randomly from not topN sources.")
    sampled_ids = np.hstack((topN, midN))
    return list(sampled_ids)


def nsr_sampling2(predictions_df: pd.DataFrame,
                 score_column: str = 'pred',
                 Nhi: int = 3,
                 Nmid: int = 10,
                 Nlow: int = 2,
                 hi_bracket: tuple = (0.9, 1.0),
                 mid_bracket: tuple = (0.4, 0.6),
                 low_bracket: tuple = (0.0, 0.1),
                 ) -> list:
    """Not So-Random Sampling (NSR Sampling)

    With default values, selects the top 5 (Ntop) scoring samples and 10 (Nmid) random samples
    from a bracket (0.4,0.6) ofmid-range scores.
    
    Parameters
    ----------
    predictions_df : pd.DataFrame
        DataFrame with at lease the `diaSourceId` and score columns.
    score_column : str
        Name of the column containing the prediction scores.
    Ntop : int
        Number of top scoring samples to select.
    Nmid : int
        Number of mid-range scoring samples to randomly select.
    mid_bracket : tuple
        Score range for mid-range sampling (inclusive).

    Returns
    -------
    list
        List of selected `diaSourceId`s.
    """
    sorted_predictions = predictions_df.sort_values(score_column, ascending=False)
    try:
        topN = sorted_predictions[(sorted_predictions[score_column]>hi_bracket[0]) 
                    & (sorted_predictions[score_column]<hi_bracket[1])].sample(Nhi).diaSourceId.values
    except ValueError:
        topN = sorted_predictions.iloc[:Nhi].diaSourceId.values
        print(f"Warning: Not enough samples in hi_bracket {hi_bracket}, sampling randomly from top sources.")

    try:
        midN = sorted_predictions[(sorted_predictions[score_column]>mid_bracket[0]) 
                    & (sorted_predictions[score_column]<mid_bracket[1])].sample(Nmid).diaSourceId.values
    except ValueError:
        midN = sorted_predictions.iloc[Nhi:-Nlow].diaSourceId.sample(Nmid).values
        print(f"Warning: Not enough samples in mid_bracket {mid_bracket}, sampling randomly from not topN sources.")
    
    try:
        lowN = sorted_predictions[(sorted_predictions[score_column]>low_bracket[0]) 
                    & (sorted_predictions[score_column]<low_bracket[1])].sample(Nlow).diaSourceId.values
    except ValueError:
        lowN = sorted_predictions.iloc[-Nlow:].diaSourceId.values
        print(f"Warning: Not enough samples in low_bracket {low_bracket}, sampling randomly from low sources.")

    sampled_ids = np.hstack((topN, midN, lowN))
    return list(sampled_ids)


def random_sampling(predictions_df: pd.DataFrame,
                    score_column: str,
                    N: int = 15,
                    ) -> list:
    """Random Sampling"""
    sampled_ids = predictions_df.sample(N).diaSourceId.values
    return list(sampled_ids)

