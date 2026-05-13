from datetime import datetime

import pandas as pd
import pytest

from lvra.training import learning_utils as lu


def _pool_df():
    return pd.DataFrame(
        {
            "diaSourceId": ["s1", "s2", "s3"],
            "diaObjectId": ["o1", "o2", "o3"],
            "feature": [1.0, 2.0, 3.0],
        }
    )


def _labels_df():
    return pd.DataFrame(
        {
            "diaSourceId": ["s1", "s2", "s3"],
            "diaObjectId": ["o1", "o2", "o3"],
            "label": ["real", "bogus", "skip_me"],
        }
    )


def _training_ids_df(ids=("s1", "s2", "s3")):
    return pd.DataFrame(
        {
            "diaSourceId": list(ids),
            "diaObjectId": [f"o{i + 1}" for i in range(len(ids))],
        }
    )


def test_make_training_sample_aligns_features_and_targets_on_diasourceid():
    X_train, y_train = lu.make_training_sample(
        X_pool=_pool_df(),
        y_labels=_labels_df(),
        training_Ids=_training_ids_df(),
    )

    assert X_train.index.tolist() == ["s1", "s2"]
    assert X_train["feature"].tolist() == [1.0, 2.0]
    assert y_train.to_dict() == {"s1": 1, "s2": 0}
    assert y_train.name == "target"


def test_make_training_sample_converts_numeric_ids_to_strings():
    X_pool = pd.DataFrame(
        {
            "diaSourceId": [1, 2],
            "diaObjectId": [11, 22],
            "feature": [10.0, 20.0],
        }
    )
    y_labels = pd.DataFrame(
        {
            "diaSourceId": [1, 2],
            "diaObjectId": [11, 22],
            "label": ["real", "bogus"],
        }
    )
    training_ids = pd.DataFrame({"diaSourceId": [1, 2], "diaObjectId": [11, 22]})

    X_train, y_train = lu.make_training_sample(X_pool, y_labels, training_ids)

    assert X_train.index.tolist() == ["1", "2"]
    assert y_train.to_dict() == {"1": 1, "2": 0}


def test_make_training_sample_ignores_unmapped_labels_when_valid_labels_remain():
    X_train, y_train = lu.make_training_sample(
        X_pool=_pool_df(),
        y_labels=_labels_df(),
        training_Ids=_training_ids_df(),
        mapping={"real": 1, "bogus": 0},
    )

    assert X_train["diaSourceId"].tolist() == ["s1", "s2"]
    assert y_train.tolist() == [1, 0]


def test_make_training_sample_raises_when_no_labels_map_to_targets():
    labels = _labels_df()
    labels["label"] = ["unknown", "ignored", "other"]

    with pytest.raises(ValueError, match="no labels mapped"):
        lu.make_training_sample(_pool_df(), labels, _training_ids_df())


def test_make_training_sample_raises_when_no_pool_rows_match_labels():
    X_pool = pd.DataFrame(
        {
            "diaSourceId": ["x1", "x2"],
            "diaObjectId": ["ox1", "ox2"],
            "feature": [1.0, 2.0],
        }
    )

    with pytest.raises(ValueError, match="No matching rows"):
        lu.make_training_sample(
            X_pool=X_pool,
            y_labels=_labels_df(),
            training_Ids=_training_ids_df(ids=("s1",)),
        )


def test_make_training_sample_raises_for_missing_required_columns():
    labels = pd.DataFrame({"diaSourceId": ["s1"], "diaObjectId": ["o1"]})

    with pytest.raises(KeyError):
        lu.make_training_sample(_pool_df(), labels, _training_ids_df())


def test_make_training_sample_raises_for_non_dataframe_inputs():
    with pytest.raises(ValueError, match="must be a pandas DataFrame"):
        lu.make_training_sample([], _labels_df(), _training_ids_df())


def test_load_config_returns_yaml_mapping(tmp_path):
    config_path = tmp_path / "config.yaml"
    config_path.write_text("EXPERIMENT: r0b\nMODEL_PARAMS:\n  random_state: 42\n", encoding="utf-8")

    assert lu.load_config(config_path) == {
        "EXPERIMENT": "r0b",
        "MODEL_PARAMS": {"random_state": 42},
    }


def test_load_config_rejects_missing_or_non_mapping_yaml(tmp_path):
    with pytest.raises(FileNotFoundError):
        lu.load_config(tmp_path / "missing.yaml")

    config_path = tmp_path / "config.yaml"
    config_path.write_text("- not\n- a\n- mapping\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mapping"):
        lu.load_config(config_path)


def test_load_pool_parquet_validates_required_identifier_columns(tmp_path):
    pytest.importorskip("fastparquet")
    pool_path = tmp_path / "X_pool.parquet"
    _pool_df().to_parquet(pool_path, index=False, engine="fastparquet")

    loaded = lu.load_pool_parquet(pool_path)
    assert loaded["diaSourceId"].tolist() == ["s1", "s2", "s3"]

    bad_path = tmp_path / "bad.parquet"
    pd.DataFrame({"feature": [1]}).to_parquet(bad_path, index=False, engine="fastparquet")
    with pytest.raises(ValueError, match="diaSourceId"):
        lu.load_pool_parquet(bad_path)


def test_load_pool_parquet_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        lu.load_pool_parquet(tmp_path / "missing.parquet")


def test_load_labels_csv_validates_required_columns(tmp_path):
    labels_path = tmp_path / "labels.csv"
    _labels_df().to_csv(labels_path, index=False)

    loaded = lu.load_labels_csv(labels_path)
    assert loaded["diaSourceId"].tolist() == ["s1", "s2", "s3"]
    assert loaded["label"].tolist() == ["real", "bogus", "skip_me"]

    missing_label = tmp_path / "missing_label.csv"
    pd.DataFrame({"diaSourceId": ["s1"]}).to_csv(missing_label, index=False)
    with pytest.raises(ValueError, match="label"):
        lu.load_labels_csv(missing_label)

    missing_id = tmp_path / "missing_id.csv"
    pd.DataFrame({"label": ["real"]}).to_csv(missing_id, index=False)
    with pytest.raises(ValueError, match="diaSourceId"):
        lu.load_labels_csv(missing_id)


def test_load_labels_csv_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        lu.load_labels_csv(tmp_path / "missing.csv")


def test_load_metrics_returns_empty_schema_or_existing_file(tmp_path):
    df, path = lu.load_metrics("model_a", tmp_path)

    assert path == tmp_path / "model_a.metrics.csv"
    assert list(df.columns) == [
        "round",
        "accuracy",
        "precision",
        "recall",
        "f1-score",
        "timestamp",
        "model_flavour",
    ]
    assert df.empty

    existing = pd.DataFrame({"round": [1], "accuracy": [0.75]})
    existing.to_csv(path)
    loaded, _ = lu.load_metrics("model_a", tmp_path)
    assert loaded["accuracy"].tolist() == [0.75]


def test_load_trainingids_returns_round_and_existing_data(tmp_path):
    missing_path = tmp_path / "trainingIds.csv"
    training_round, df = lu.load_trainingIds(missing_path)
    assert training_round == 0
    assert list(df.columns) == ["diaSourceId", "diaObjectId", "timestamp", "round"]

    existing = pd.DataFrame(
        {
            "diaSourceId": ["s1", "s2"],
            "diaObjectId": ["o1", "o2"],
            "timestamp": ["t1", "t2"],
            "round": [1, 2],
        }
    )
    existing.to_csv(missing_path)
    training_round, df = lu.load_trainingIds(missing_path)
    assert training_round == 2
    assert df["diaSourceId"].tolist() == ["s1", "s2"]


def test_update_trainingids_appends_timestamp_and_round(monkeypatch):
    class FixedDatetime:
        @staticmethod
        def utcnow():
            return datetime(2026, 1, 1, 12, 0, 0)

    monkeypatch.setattr(lu, "datetime", FixedDatetime)
    existing = pd.DataFrame(columns=["diaSourceId", "diaObjectId", "timestamp", "round"])
    sampled = pd.DataFrame({"diaSourceId": ["s1"], "diaObjectId": ["o1"]})

    updated = lu.update_trainingIds(sampled, 3, existing)

    assert updated.loc[0, "diaSourceId"] == "s1"
    assert updated.loc[0, "timestamp"] == "2026-01-01T12:00:00"
    assert updated.loc[0, "round"] == 3


def test_resolve_model_name_uses_params_and_default_sampling_strategy():
    cfg = {
        "EXPERIMENT": "r0b",
        "MODEL_PARAMS": {"learning_rate": 0.1, "max_iter": 50, "random_state": 42},
        "SAMPLING_STRATEGY": "nsr",
    }
    assert lu.resolve_model_name(cfg) == "r0b_LR0p1_MaxI50_RS42_SSnsr"

    cfg.pop("SAMPLING_STRATEGY")
    assert lu.resolve_model_name(cfg) == "r0b_LR0p1_MaxI50_RS42_SSUNK"
