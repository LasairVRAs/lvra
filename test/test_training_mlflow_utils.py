# tests/test_mlflow_utils.py
import mlflow
from lvra.training.mlflow_utils import load_config, setup_mlflow
from lvra.training import mlflow_utils as mu
import pandas as pd

def test_load_training_sample_basic(tmp_path):
    # Create simple X_pool with diaSourceId column
    X = pd.DataFrame({
        "diaSourceId": [101, 102, 103, 104],
        "f1": [0.1, 0.2, 0.3, 0.4],
        "f2": [1, 2, 3, 4]
    })
    # create labels DataFrame with some entries (string labels)
    y = pd.DataFrame({
        "diaSourceId": [101, 103],
        "diaObjectId": [1001, 1003],
        "label": ["real", "bogus"]
    })

    X_train, y_train = mu.load_training_sample(X, y, mapping={'real':1, 'bogus':0})
    # Expect X_train rows for 101 and 103 only
    assert sorted(list(X_train.index)) == ["101", "103"]
    # y_train aligned and values correct
    assert list(y_train.astype(int)) == [1, 0]
    assert y_train.name == 'target'


def make_temp_config(tmp_path, experiment_name="test_exp"):
    # Use a local file-based mlflow store
    mlruns_dir = tmp_path / "mlruns"
    tracking_uri = f"file://{mlruns_dir.as_posix()}"
    cfg = {
        "EXPERIMENT": experiment_name,
        "TRACKING_URI": tracking_uri,
        # add other keys your code expects if needed
    }
    cfg_path = tmp_path / "cfg.yaml"
    with cfg_path.open("w") as fh:
        import yaml
        yaml.safe_dump(cfg, fh)
    return cfg_path, cfg, mlruns_dir

def test_load_config_and_setup_mlflow_no_previous_run(tmp_path):
    cfg_path, cfg, mlruns_dir = make_temp_config(tmp_path, "exp_no_prev")
    loaded = load_config(str(cfg_path))
    client, exp_id, last_run = setup_mlflow(loaded)
    assert client is not None
    assert exp_id is not None
    assert last_run is None  # no run created yet

def test_setup_mlflow_with_previous_finished_run(tmp_path):
    cfg_path, cfg, mlruns_dir = make_temp_config(tmp_path, "exp_with_prev")

    # Load and setup
    loaded = load_config(str(cfg_path))
    client, exp_id, last_run = setup_mlflow(loaded)
    assert last_run is None

    # Create a finished run in that experiment
    mlflow.set_tracking_uri(loaded['TRACKING_URI'])
    mlflow.set_experiment(loaded['EXPERIMENT'])
    with mlflow.start_run():
        mlflow.log_param("p", 1)
        mlflow.log_metric("m", 0.5)

    # Re-run setup and expect to find the finished run
    client2, exp_id2, last_run2 = setup_mlflow(loaded)
    assert client2 is not None
    assert exp_id2 == exp_id
    assert last_run2 is not None
    assert "run_id" in last_run2
    assert "metrics" in last_run2
    assert last_run2["metrics"].get("m") == 0.5
