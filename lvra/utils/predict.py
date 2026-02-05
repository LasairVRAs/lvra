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





