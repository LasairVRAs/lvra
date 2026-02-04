# INPUT: 
# - stems (from the annotator or the script that calls our predictor)
# - model path
# - model name 
# - model version 

import pandas as pd
import joblib

def predict(df, 
            model,
            logger
            ):
    
    if not isinstance(df, pd.DataFrame):
        return None, 23 #input file type incorrect 
    
    trained_features = list(model.feature_names_in)
    if len(set(trained_features) - set(df.columns))==0:
        # then all the features we trained on are in the columns of the df we were given
        pass
    else:
        return None, 31 # input features are missing

    X=df[trained_features]
    preds = model.predict_proba(X).T[1]

    scores_df = df[['diaObjectId', 'diaSourceId']].copy()
    scores_df['score'] = preds
    
    return scores_df, 0





