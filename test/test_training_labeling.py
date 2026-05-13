# tests/test_labeling.py
import importlib
import os
import sys
from pathlib import Path
import pandas as pd
import pytest
import logging

# Helper to import the module after setting LVRA_TRAINING_ROOTDIR
def _reload_labeling_module(tmp_path: Path):
    os.environ["LVRA_TRAINING_ROOTDIR"] = str(tmp_path)

    root = str(tmp_path)
    if root not in sys.path:
        sys.path.insert(0, root)

    modname = "lvra.training.labeling"
    # force fresh import
    for k in list(sys.modules.keys()):
        if k == modname or k.startswith(modname + "."):
            del sys.modules[k]
    return importlib.import_module(modname)


@pytest.fixture(autouse=True)
def clear_logging_handlers():
    """Remove handlers from the root logger and the module logger to ensure
    each test's logging writes to the test tmp dir."""
    # remove root handlers
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    # remove any named logger handlers (safety)
    for logger_name in ("lvra.training.labeling", "lvra.training"):
        lg = logging.getLogger(logger_name)
        for h in list(lg.handlers):
            lg.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

    yield

    # cleanup again after test
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass
    for logger_name in ("lvra.training.labeling", "lvra.training"):
        lg = logging.getLogger(logger_name)
        for h in list(lg.handlers):
            lg.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass


def write_pool_csv(path: Path, df: pd.DataFrame):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def test_interactive_labeling_basic(tmp_path):
    """
    Basic flow: two rows, inputs label both (r and g). Check output CSV contains
    two rows with the canonical labels and session_id present.
    """
    labeling = _reload_labeling_module(tmp_path)

    # create a small pool with two alerts
    pool = pd.DataFrame({
        "diaSourceId": ["s1", "s2"],
        "diaObjectId": ["o1", "o2"],
    })

    out_path = tmp_path / "pool" / "y_pool.csv"

    # inputs: first 'r' => 'real', second 'g' => 'gal'
    inputs = iter(["r", "g"])

    called_urls = []
    def fake_opener(url):
        called_urls.append(url)

    def fake_input(prompt):
        try:
            return next(inputs)
        except StopIteration:
            return "q"

    # run interactive labeling (sleep=0 to avoid delay)
    labeling.interactive_labeling(
        df_pool=pool,
        output=str(out_path),
        input_func=fake_input,
        opener=fake_opener,
        session_id="testsess",
        sleep=0,
    )

    # function returns None in current implementation; check output file instead
    assert out_path.exists(), "label output CSV must be created"

    df_out = pd.read_csv(out_path, dtype=str)
    assert set(df_out["diaSourceId"].astype(str)) == {"s1", "s2"}
    assert set(df_out["label"].astype(str)) == {"real", "gal"}
    # session_id column present and equals testsess in every row
    assert all(df_out["session_id"] == "testsess")
    # opener was called twice with URLs for o1 and o2
    assert len(called_urls) == 2
    assert "o1" in called_urls[0] and "o2" in called_urls[1]


def test_interactive_labeling_resume_skips_existing(tmp_path):
    """
    If resume=True and an existing output CSV contains 's1', the function
    should skip 's1' and only present 's2'.
    """
    labeling = _reload_labeling_module(tmp_path)

    pool_dir = tmp_path / "pool"
    pool_dir.mkdir(parents=True, exist_ok=True)
    out_path = pool_dir / "y_pool.csv"

    # pre-create existing labels with s1
    existing = pd.DataFrame([{
        "diaSourceId": "s1",
        "diaObjectId": "o1",
        "label": "real",
        "timestamp": "2020-01-01T00:00:00",
        "session_id": "oldsess",
        "url": "http://example",
    }])
    existing.to_csv(out_path, index=False)

    pool = pd.DataFrame({
        "diaSourceId": ["s1", "s2"],
        "diaObjectId": ["o1", "o2"],
    })

    inputs = iter(["r"])  # only one label expected (for s2)
    def fake_input(prompt):
        try:
            return next(inputs)
        except StopIteration:
            return "q"

    called = []
    def fake_opener(url):
        called.append(url)

    labeling.interactive_labeling(
        df_pool=pool,
        output=str(out_path),
        input_func=fake_input,
        opener=fake_opener,
        session_id="sess2",
        sleep=0,
    )

    # Read final CSV and assert we now have two rows (existing + new)
    df_final = pd.read_csv(out_path, dtype=str)
    assert set(df_final["diaSourceId"]) == {"s1", "s2"}
    # ensure the old row was preserved and session_id preserved for old row
    old = df_final[df_final["diaSourceId"] == "s1"].iloc[0]
    assert old["session_id"] == "oldsess"
    # new label row has session_id 'sess2'
    new = df_final[df_final["diaSourceId"] == "s2"].iloc[0]
    assert new["session_id"] == "sess2"
    assert new["label"] == "real"


def test_interactive_labeling_keyboard_interrupt_saves_progress(tmp_path):
    """
    Simulate a KeyboardInterrupt during input_func; the code catches KeyboardInterrupt,
    saves progress and exits. We'll simulate input_func that returns one label then
    raises KeyboardInterrupt.
    """
    labeling = _reload_labeling_module(tmp_path)

    pool = pd.DataFrame({
        "diaSourceId": ["s1", "s2", "s3"],
        "diaObjectId": ["o1", "o2", "o3"],
    })
    out_path = tmp_path / "pool" / "y_pool.csv"

    state = {"count": 0}
    def fake_input(prompt):
        if state["count"] == 0:
            state["count"] += 1
            return "r"
        else:
            # simulate user pressing Ctrl-C
            raise KeyboardInterrupt

    def fake_opener(url):
        return None

    labeling.interactive_labeling(
        df_pool=pool,
        output=str(out_path),
        input_func=fake_input,
        opener=fake_opener,
        session_id="ki-session",
        sleep=0,
    )

    # file should exist and contain exactly 1 labeled row (the one before interrupt)
    assert out_path.exists()
    df_final = pd.read_csv(out_path, dtype=str)
    assert len(df_final) == 1
    assert df_final.iloc[0]["diaSourceId"] == "s1"
    assert df_final.iloc[0]["session_id"] == "ki-session"
    assert df_final.iloc[0]["label"] == "real"


def test_load_labels_returns_empty_canonical_dataframe_for_missing_file(tmp_path):
    labeling = _reload_labeling_module(tmp_path)

    df = labeling.load_labels(tmp_path / "pool" / "missing.csv")

    assert list(df.columns) == labeling.LABELFILE_COLUMNS
    assert df.empty


def test_interactive_labeling_rejects_non_dataframe_input(tmp_path):
    labeling = _reload_labeling_module(tmp_path)

    with pytest.raises(TypeError, match="pandas DataFrame"):
        labeling.interactive_labeling(
            df_pool=[],
            output=str(tmp_path / "pool" / "labels.csv"),
            sleep=0,
        )


def test_interactive_labeling_rejects_missing_required_columns(tmp_path):
    labeling = _reload_labeling_module(tmp_path)
    pool = pd.DataFrame({"diaSourceId": ["s1"]})

    with pytest.raises(ValueError, match="diaObjectId"):
        labeling.interactive_labeling(
            df_pool=pool,
            output=str(tmp_path / "pool" / "labels.csv"),
            sleep=0,
        )


def test_interactive_labeling_invalid_label_reprompts_then_saves_valid_label(tmp_path):
    labeling = _reload_labeling_module(tmp_path)
    pool = pd.DataFrame({"diaSourceId": ["s1"], "diaObjectId": ["o1"]})
    out_path = tmp_path / "pool" / "labels.csv"
    inputs = iter(["bad", "b"])
    opened = []

    labeling.interactive_labeling(
        df_pool=pool,
        output=str(out_path),
        input_func=lambda prompt: next(inputs),
        opener=lambda url: opened.append(url),
        session_id="invalid-then-valid",
        sleep=0,
    )

    df_out = pd.read_csv(out_path, dtype=str)
    assert df_out["label"].tolist() == ["bogus"]
    assert df_out["session_id"].tolist() == ["invalid-then-valid"]
    assert len(opened) == 2


def test_interactive_labeling_skip_empty_and_quit_do_not_create_labels(tmp_path):
    labeling = _reload_labeling_module(tmp_path)
    pool = pd.DataFrame(
        {
            "diaSourceId": ["s1", "s2", "s3"],
            "diaObjectId": ["o1", "o2", "o3"],
        }
    )
    out_path = tmp_path / "pool" / "labels.csv"
    inputs = iter(["s", "", "q"])

    labeling.interactive_labeling(
        df_pool=pool,
        output=str(out_path),
        input_func=lambda prompt: next(inputs),
        opener=lambda url: None,
        session_id="skip-empty-quit",
        sleep=0,
    )

    assert not out_path.exists()


def test_interactive_labeling_opener_failure_does_not_block_label_save(tmp_path):
    labeling = _reload_labeling_module(tmp_path)
    pool = pd.DataFrame({"diaSourceId": ["s1"], "diaObjectId": ["o1"]})
    out_path = tmp_path / "pool" / "labels.csv"

    def failing_opener(url):
        raise RuntimeError("browser failed")

    labeling.interactive_labeling(
        df_pool=pool,
        output=str(out_path),
        input_func=lambda prompt: "r",
        opener=failing_opener,
        session_id="opener-failure",
        sleep=0,
    )

    df_out = pd.read_csv(out_path, dtype=str)
    assert df_out["diaSourceId"].tolist() == ["s1"]
    assert df_out["label"].tolist() == ["real"]


def test_interactive_labeling_resume_false_replaces_existing_output(tmp_path):
    labeling = _reload_labeling_module(tmp_path)
    out_path = tmp_path / "pool" / "labels.csv"
    out_path.parent.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "diaSourceId": "old",
                "diaObjectId": "old-object",
                "label": "bogus",
                "timestamp": "old-time",
                "session_id": "old-session",
                "url": "old-url",
            }
        ]
    ).to_csv(out_path, index=False)

    pool = pd.DataFrame({"diaSourceId": ["s1"], "diaObjectId": ["o1"]})
    labeling.interactive_labeling(
        df_pool=pool,
        output=str(out_path),
        input_func=lambda prompt: "r",
        opener=lambda url: None,
        session_id="new-session",
        resume=False,
        sleep=0,
    )

    df_out = pd.read_csv(out_path, dtype=str)
    assert df_out["diaSourceId"].tolist() == ["s1"]
    assert df_out["session_id"].tolist() == ["new-session"]
