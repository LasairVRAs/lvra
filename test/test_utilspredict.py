"""
Unit tests for lvra.utils.predict module.

Tests the prediction function with various input scenarios,
model validation, and error handling.
"""

import pytest
from unittest.mock import Mock
import pandas as pd
import numpy as np

from lvra.utils import predict


# #-#-#-#-#-#-#-# #
#     FIXTURES     #
# #-#-#-#-#-#-#-# #

@pytest.fixture
def mock_logger():
    """Return a mock logger for testing."""
    return Mock()


@pytest.fixture
def mock_model():
    """Return a mock trained model."""
    model = Mock()
    # Simulate a model trained on 3 features
    model.feature_names_in_ = np.array(['feature_1', 'feature_2', 'feature_3'])
    # Mock predict_proba to return probabilities
    # Returns shape (n_samples, 2) for binary classification
    model.predict_proba = Mock()
    return model


@pytest.fixture
def valid_dataframe():
    """Return a valid DataFrame with all required features."""
    return pd.DataFrame({
        'diaObjectId': ['ZTF21aaa', 'ZTF21bbb', 'ZTF21ccc'],
        'diaSourceId': [1001, 1002, 1003],
        'feature_1': [0.5, 0.6, 0.7],
        'feature_2': [1.2, 1.3, 1.4],
        'feature_3': [2.1, 2.2, 2.3],
        'extra_feature': [9, 9, 9]  # Extra features are fine
    })


# #-#-#-#-#-#-#-#-#-#-#-# #
#   TESTS: predict()      #
# #-#-#-#-#-#-#-#-#-#-#-# #

class TestPredictHappyPath:
    """Tests for successful prediction scenarios."""
    
    def test_successful_prediction(
        self,
        valid_dataframe,
        mock_model,
        mock_logger
    ):
        """Test that valid input produces correct predictions."""
        # Mock model predictions (probability of class 1)
        mock_model.predict_proba.return_value = np.array([
            [0.3, 0.7],  # 70% probability for class 1
            [0.4, 0.6],  # 60% probability for class 1
            [0.2, 0.8]   # 80% probability for class 1
        ])
        
        result, status_code = predict.predict(
            df=valid_dataframe,
            model=mock_model,
            logger=mock_logger
        )
        
        # Verify success
        assert status_code == 0
        assert result is not None
        assert isinstance(result, pd.DataFrame)
        
        # Verify output structure
        assert list(result.columns) == ['diaObjectId', 'diaSourceId', 'score']
        assert len(result) == 3
        
        # Verify scores match predictions
        assert result['score'].tolist() == [0.7, 0.6, 0.8]
        
        # Verify IDs are preserved
        assert result['diaObjectId'].tolist() == ['ZTF21aaa', 'ZTF21bbb', 'ZTF21ccc']
        assert result['diaSourceId'].tolist() == [1001, 1002, 1003]
        
        # Verify model was called with correct features
        mock_model.predict_proba.assert_called_once()
        call_args = mock_model.predict_proba.call_args[0][0]
        assert list(call_args.columns) == ['feature_1', 'feature_2', 'feature_3']


    def test_prediction_with_extra_columns(
        self,
        mock_model,
        mock_logger
    ):
        """Test that extra columns in input DataFrame don't cause issues."""
        # DataFrame with many extra columns
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
            'feature_1': [0.5],
            'feature_2': [1.2],
            'feature_3': [2.1],
            'extra_col_1': [100],
            'extra_col_2': [200],
            'extra_col_3': [300],
        })
        
        mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        # Should succeed
        assert status_code == 0
        assert result is not None
        
        # Model should only receive the 3 trained features
        call_args = mock_model.predict_proba.call_args[0][0]
        assert list(call_args.columns) == ['feature_1', 'feature_2', 'feature_3']
        assert len(call_args.columns) == 3


    def test_prediction_preserves_row_order(
        self,
        mock_model,
        mock_logger
    ):
        """Test that output rows match input row order."""
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21zzz', 'ZTF21aaa', 'ZTF21mmm'],
            'diaSourceId': [9999, 1111, 5555],
            'feature_1': [0.1, 0.2, 0.3],
            'feature_2': [1.1, 1.2, 1.3],
            'feature_3': [2.1, 2.2, 2.3],
        })
        
        mock_model.predict_proba.return_value = np.array([
            [0.5, 0.5],
            [0.4, 0.6],
            [0.3, 0.7]
        ])
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        # Verify order is preserved
        assert result['diaObjectId'].tolist() == ['ZTF21zzz', 'ZTF21aaa', 'ZTF21mmm']
        assert result['diaSourceId'].tolist() == [9999, 1111, 5555]
        assert result['score'].tolist() == [0.5, 0.6, 0.7]


    def test_single_row_prediction(
        self,
        mock_model,
        mock_logger
    ):
        """Test prediction with a single row DataFrame."""
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
            'feature_1': [0.5],
            'feature_2': [1.2],
            'feature_3': [2.1],
        })
        
        mock_model.predict_proba.return_value = np.array([[0.25, 0.75]])
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        assert status_code == 0
        assert len(result) == 1
        assert result['score'].iloc[0] == 0.75


    def test_large_batch_prediction(
        self,
        mock_model,
        mock_logger
    ):
        """Test prediction with a large batch of data."""
        n_rows = 1000
        df = pd.DataFrame({
            'diaObjectId': [f'ZTF21{i:04d}' for i in range(n_rows)],
            'diaSourceId': list(range(n_rows)),
            'feature_1': np.random.rand(n_rows),
            'feature_2': np.random.rand(n_rows),
            'feature_3': np.random.rand(n_rows),
        })
        
        # Generate random predictions
        predictions = np.random.rand(n_rows, 2)
        predictions = predictions / predictions.sum(axis=1, keepdims=True)  # Normalize
        mock_model.predict_proba.return_value = predictions
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        assert status_code == 0
        assert len(result) == n_rows
        assert list(result.columns) == ['diaObjectId', 'diaSourceId', 'score']


class TestPredictInputValidation:
    """Tests for input validation and error handling."""
    
    def test_non_dataframe_input_returns_error(
        self,
        mock_model,
        mock_logger
    ):
        """Test that non-DataFrame input returns status code 23."""
        # Test with various non-DataFrame types
        invalid_inputs = [
            None,
            "not a dataframe",
            [1, 2, 3],
            {'key': 'value'},
            42,
        ]
        
        for invalid_input in invalid_inputs:
            result, status_code = predict.predict(
                df=invalid_input,
                model=mock_model,
                logger=mock_logger
            )
            
            assert status_code == 23, f"Failed for input type: {type(invalid_input)}"
            assert result is None
            
            # Verify error was logged
            mock_logger.error.assert_called()
            error_msg = mock_logger.error.call_args[0][0]
            assert "[PREDICT] Input data is not a pandas DataFrame" in error_msg
            assert "status_code=23" in error_msg
            
            mock_logger.reset_mock()


    def test_missing_required_features_returns_error(
        self,
        mock_model,
        mock_logger
    ):
        """Test that missing required features returns status code 31."""
        # DataFrame missing 'feature_3'
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
            'feature_1': [0.5],
            'feature_2': [1.2],
            # 'feature_3' is missing!
        })
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        assert status_code == 31
        assert result is None
        
        # Verify error was logged
        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        assert "[PREDICT] Input data is missing features required by the model" in error_msg
        assert "status_code=31" in error_msg


    def test_missing_multiple_features_returns_error(
        self,
        mock_model,
        mock_logger
    ):
        """Test that missing multiple features returns status code 31."""
        # DataFrame missing both 'feature_2' and 'feature_3'
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
            'feature_1': [0.5],
            # 'feature_2' and 'feature_3' are missing!
        })
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        assert status_code == 31
        assert result is None


    def test_missing_diaObjectId_column(
        self,
        mock_model,
        mock_logger
    ):
        """Test behavior when diaObjectId column is missing."""
        df = pd.DataFrame({
            # 'diaObjectId' is missing!
            'diaSourceId': [1001],
            'feature_1': [0.5],
            'feature_2': [1.2],
            'feature_3': [2.1],
        })
        
        mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])
        
        # Should raise KeyError when trying to copy diaObjectId
        with pytest.raises(KeyError):
            predict.predict(
                df=df,
                model=mock_model,
                logger=mock_logger
            )


    def test_missing_diaSourceId_column(
        self,
        mock_model,
        mock_logger
    ):
        """Test behavior when diaSourceId column is missing."""
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            # 'diaSourceId' is missing!
            'feature_1': [0.5],
            'feature_2': [1.2],
            'feature_3': [2.1],
        })
        
        mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])
        
        # Should raise KeyError when trying to copy diaSourceId
        with pytest.raises(KeyError):
            predict.predict(
                df=df,
                model=mock_model,
                logger=mock_logger
            )


    def test_empty_dataframe(
        self,
        mock_model,
        mock_logger
    ):
        """Test behavior with an empty DataFrame."""
        df = pd.DataFrame({
            'diaObjectId': [],
            'diaSourceId': [],
            'feature_1': [],
            'feature_2': [],
            'feature_3': [],
        })
        
        mock_model.predict_proba.return_value = np.array([]).reshape(0, 2)
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        # Should succeed but return empty result
        assert status_code == 0
        assert len(result) == 0
        assert list(result.columns) == ['diaObjectId', 'diaSourceId', 'score']


class TestFeatureMatching:
    """Tests for feature name matching logic."""
    
    def test_features_in_different_order(
        self,
        mock_model,
        mock_logger
    ):
        """Test that feature order in DataFrame doesn't matter."""
        # DataFrame with features in different order than model expects
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
            'feature_3': [2.1],  # Different order
            'feature_1': [0.5],
            'feature_2': [1.2],
        })
        
        mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        # Should succeed
        assert status_code == 0
        
        # Verify features were passed to model in correct order
        call_args = mock_model.predict_proba.call_args[0][0]
        assert list(call_args.columns) == ['feature_1', 'feature_2', 'feature_3']


    def test_exact_feature_set_match(
        self,
        mock_model,
        mock_logger
    ):
        """Test with DataFrame having exactly the required features, no more."""
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
            'feature_1': [0.5],
            'feature_2': [1.2],
            'feature_3': [2.1],
            # No extra features
        })
        
        mock_model.predict_proba.return_value = np.array([[0.3, 0.7]])
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        assert status_code == 0
        assert result is not None


    def test_feature_name_case_sensitivity(
        self,
        mock_model,
        mock_logger
    ):
        """Test that feature names are case-sensitive."""
        # DataFrame with features in wrong case
        df = pd.DataFrame({
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
            'Feature_1': [0.5],  # Wrong case
            'FEATURE_2': [1.2],  # Wrong case
            'feature_3': [2.1],
        })
        
        result, status_code = predict.predict(
            df=df,
            model=mock_model,
            logger=mock_logger
        )
        
        # Should fail because feature_1 and feature_2 are "missing"
        assert status_code == 31
        assert result is None


class TestEdgeCases:
    """Tests for edge cases and unusual scenarios."""
    
    def test_model_with_many_features(
        self,
        mock_logger
    ):
        """Test with a model trained on many features."""
        # Model with 20 features
        model = Mock()
        model.feature_names_in_ = np.array([f'feature_{i}' for i in range(20)])
        
        # DataFrame with all 20 features plus extras
        df_data = {
            'diaObjectId': ['ZTF21aaa'],
            'diaSourceId': [1001],
        }
        for i in range(20):
            df_data[f'feature_{i}'] = [float(i)]
        df_data['extra'] = [999]
        
        df = pd.DataFrame(df_data)
        
        model.predict_proba.return_value = np.array([[0.3, 0.7]])
        
        result, status_code = predict.predict(
            df=df,
            model=model,
            logger=mock_logger
        )
        
        assert status_code == 0
        # Verify all 20 features were passed to model
        call_args = model.predict_proba.call_args[0][0]
        assert len(call_args.columns) == 20


    def test_prediction_scores_range(
        self,
        valid_dataframe,
        mock_model,
        mock_logger
    ):
        """Test that prediction scores are in valid probability range [0, 1]."""
        # Edge case: very confident predictions
        mock_model.predict_proba.return_value = np.array([
            [0.999, 0.001],  # Very low confidence in class 1
            [0.001, 0.999],  # Very high confidence in class 1
            [0.5, 0.5]       # Uncertain
        ])
        
        result, status_code = predict.predict(
            df=valid_dataframe,
            model=mock_model,
            logger=mock_logger
        )
        
        assert status_code == 0
        # Verify all scores are valid probabilities
        assert all(0 <= score <= 1 for score in result['score'])
        assert result['score'].tolist() == [0.001, 0.999, 0.5]


    def test_single_class_predict_proba_output_raises(
        self,
        valid_dataframe,
        mock_model,
        mock_logger
    ):
        """The production helper expects binary predict_proba output with a class-1 column."""
        mock_model.predict_proba.return_value = np.array([
            [1.0],
            [1.0],
            [1.0],
        ])

        with pytest.raises(IndexError):
            predict.predict(
                df=valid_dataframe,
                model=mock_model,
                logger=mock_logger
            )


    def test_predict_proba_row_count_mismatch_raises(
        self,
        valid_dataframe,
        mock_model,
        mock_logger
    ):
        """Prediction score count must match the input DataFrame length."""
        mock_model.predict_proba.return_value = np.array([
            [0.4, 0.6],
            [0.3, 0.7],
        ])

        with pytest.raises(ValueError):
            predict.predict(
                df=valid_dataframe,
                model=mock_model,
                logger=mock_logger
            )


    def test_model_without_feature_names_raises_attribute_error(
        self,
        valid_dataframe,
        mock_logger
    ):
        model = Mock(spec=[])

        with pytest.raises(AttributeError):
            predict.predict(
                df=valid_dataframe,
                model=model,
                logger=mock_logger
            )


# #-#-#-#-#-#-#-# #
#   EASTER EGG!   #
# #-#-#-#-#-#-#-# #

def test_machine_learning_confidence():
    """
    Machine Learning Model: "I'm 99.9% confident!"
    Also Machine Learning Model: *predicts cat as toaster*
    
    This test is 100% confident it will pass.
    (Unlike most ML models... 😄)
    """
    confidence = 1.0
    assert confidence == 1.0  # At least THIS prediction is deterministic!
