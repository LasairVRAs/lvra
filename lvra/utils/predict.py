"""Model Prediction functions
Oversight: High to Total
Accountable: Heloise

"""

import pandas as pd

def predict(df, 
            model,
            logger
            ):
    
    if not isinstance(df, pd.DataFrame):
        logger.error("[PREDICT] Input data is not a pandas DataFrame | status_code=23")
        return None, 23 #input file type incorrect 
    
    trained_features = list(model.feature_names_in_)
    if len(set(trained_features) - set(df.columns))==0:
        # then all the features we trained on are in the columns of the df we were given
        pass
    else:
        logger.error("[PREDICT] Input data is missing features required by the model | status_code=31")
        return None, 31 # input features are missing

    X=df[trained_features]
    preds = model.predict_proba(X).T[1]

    scores_df = df[['diaObjectId', 'diaSourceId']].copy()
    scores_df['score'] = preds

    return scores_df, 0


def to_model_input(df, model):
    """Takes dataframe from our alert data processing and formats it so it is valid model input.

    This exists because when we process the alerts we make one dataframe that covers all the features
    that our models might need. Now we take this super-set and only keep the features that 
    create a valid model input.
    
    Parameters
    ----------
    df : pd.DataFrame
       df of features from the alert processing
    model: sklearn model
       our model. Must have the .feature_names_in_  and .is_categorical_ attributes. 

    Return
    ------
    pd.DataFrame of the features for our model (a.k.a X)
    """

    # Grab the name of the features we need for our model
    names = list(model.feature_names_in_)

    # Categorical features
    cats = {n for n, c in zip(names, model.is_categorical_) if c}

    # Our features are either categories or floats. Even the bools are floats (1.0, or 0.0) 
    return df[names].astype({n: "category" if n in cats else float for n in names})


def predict_multiclass(df, model, logger):
    """Calculates the scores for our multi class models
    
    Parameters
    ----------
    df : pd.DataFrame
       The features dataframe from alert processing (not model specific)
    model: sklearn model
       Our model. Must have .classes_ .feature_names_in_  and .is_categorical_ attributes. 
    logger: logging.Logger
       Our logger object 

    Return
    ------
    pd.DataFrame, int
    """

    # Checks we give it a dataframe 
    if not isinstance(df, pd.DataFrame):
        logger.error("[PREDICT] Input data is not a pandas DataFrame | status_code=23")
        return None, 23

    # Checks we have the right columns
    if set(model.feature_names_in_) - set(df.columns):
        logger.error("[PREDICT] Input data is missing features required by the model | status_code=31")
        return None, 31

    # Calculate our scores (first, turn df to X with to_model_input)
    proba = model.predict_proba(to_model_input(df, model))
    # copy our diaobjectids and diasourceids to start our scores data frame
    scores_df = df[['diaObjectId', 'diaSourceId']].copy()
    # add the classes and probabilities corresponding to these classes
    scores_df[list(model.classes_)] = proba

    # WARNING: 0 is success because of BASH. This is different from my Status codes where 1 = successfully processed. 
    return scores_df, 0





