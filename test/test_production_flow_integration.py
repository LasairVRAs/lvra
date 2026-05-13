import json
import sqlite3
from datetime import datetime
from unittest.mock import Mock

import numpy as np
import pytest

import lvra.pypeline.kafka_consumer as kafka_module
import lvra.pypeline.r0b_annotator as annotator_module
import lvra.pypeline.r0b_feature_maker as feature_module
import lvra.pypeline.r0b_predict as predict_module


class FakeModel:
    feature_names_in_ = ["deltaDiaSourceMjdTai"]

    def predict_proba(self, X):
        return np.array([[0.2, 0.8] for _ in range(len(X))])


class FixedDatetime:
    @staticmethod
    def utcnow():
        return datetime(2024, 1, 15, 10, 30, 45)


class FakeLasairClient:
    def __init__(self):
        self.calls = []

    def annotate(self, topic, objectId, classification, version, explanation, classdict, url):
        self.calls.append(
            {
                "topic": topic,
                "objectId": objectId,
                "classification": classification,
                "version": version,
                "explanation": explanation,
                "classdict": classdict,
                "url": url,
            }
        )


def _kafka_message(dia_object_id, dia_source_id):
    msg = Mock()
    msg.error.return_value = None
    msg.value.return_value = json.dumps({
        "diaObjectId": dia_object_id,
        "diaSourceId": dia_source_id,
        "ra": 123.4,
        "decl": -45.6,
        "lastDiaSourceMjdTai": 59001.0,
        "firstDiaSourceMjdTai": 59000.0,
        "alert": {
            "diaSourcesList": [
                {
                    "diaObjectId": dia_object_id,
                    "diaSourceId": dia_source_id - 1,
                    "psfFlux": 1000.0,
                    "midpointMjdTai": 59000.0,
                },
                {
                    "diaObjectId": dia_object_id,
                    "diaSourceId": dia_source_id,
                    "psfFlux": 6000.0,
                    "midpointMjdTai": 59001.0,
                },
            ]
        },
    })
    return msg


@pytest.mark.integration
def test_local_runtime_flow_from_kafka_to_annotation(monkeypatch, tmp_path, log_db_path):
    """Run the production Python stages against local fakes and the canonical DB schema."""
    stem = "20240115_103045"
    date = stem[:8]
    json_root = tmp_path / "JSON"
    csv_root = tmp_path / "csv"
    kafka_json_dir = json_root / date
    kafka_json_dir.mkdir(parents=True)
    csv_root.mkdir(parents=True)

    common_setup = {
        "kafka_server": "kafka.example:9092",
        "group_id": "pytest",
        "my_topic": "lvra-test",
        "log_db": log_db_path,
        "endpoint": "https://example.invalid/api",
    }
    kafka_setup = {
        **common_setup,
        "json_dir": kafka_json_dir,
    }
    file_stage_setup = {
        **common_setup,
        "json_dir": json_root / "placeholder",
        "csv_dir": csv_root / "placeholder",
    }
    model_config = {
        "MODEL_PATH": str(tmp_path / "fake-model.joblib"),
        "MODEL_NAME": "r0b",
        "MODEL_VERSION": "vtest",
        "TOPIC_OUT": "pytest-topic",
        "EXPLANATION": "pytest explanation",
        "URL": "https://example.invalid/model",
    }

    consumer = Mock()
    consumer.poll.side_effect = [
        _kafka_message(170000000000000001, 170000000000000101),
        None,
    ]
    monkeypatch.setattr(kafka_module, "set_up", lambda settings_path, log_name, logger: kafka_setup)
    monkeypatch.setattr(kafka_module, "lasair_consumer", lambda server, group_id, topic: consumer)
    monkeypatch.setattr(kafka_module, "datetime", FixedDatetime)

    assert kafka_module.main() == 0

    monkeypatch.setattr(feature_module, "set_up", lambda settings_path, log_name, logger: file_stage_setup)
    assert feature_module.main() == 0

    monkeypatch.setattr(predict_module, "set_up", lambda settings_path, log_name, logger: file_stage_setup)
    monkeypatch.setattr(predict_module, "read_model_config", lambda path, logger: (model_config, 0))
    monkeypatch.setattr(predict_module.joblib, "load", lambda path: FakeModel())
    assert predict_module.main() == 0

    fake_lasair = FakeLasairClient()
    monkeypatch.setattr(annotator_module, "LASAIR_TOKEN", "pytest-token")
    monkeypatch.setattr(annotator_module, "set_up", lambda settings_path, log_name, logger: file_stage_setup)
    monkeypatch.setattr(annotator_module, "read_model_config", lambda path, logger: (model_config, 0))
    monkeypatch.setattr(annotator_module.lasair, "lasair_client", lambda token, endpoint: fake_lasair)
    assert annotator_module.main() == 0

    with sqlite3.connect(log_db_path) as con:
        assert con.execute("SELECT stem, r0b FROM feature_making").fetchall() == [(stem, 1)]
        assert con.execute("SELECT stem, r0b FROM predict").fetchall() == [(stem, 1)]
        assert con.execute("SELECT stem, r0b FROM annotating").fetchall() == [(stem, 1)]
        assert con.execute("SELECT diaObjectId, stem FROM diaobjid_stems").fetchall() == [
            (170000000000000001, stem)
        ]
        assert con.execute("SELECT diaObjectId, diaSourceId, score FROM provenance").fetchall() == [
            (170000000000000001, 170000000000000101, 0.8)
        ]
        threshold_rows = con.execute(
            "SELECT diaObjectId, diaSourceId, n_gt22, brighter22, first22 "
            "FROM threshold_flags_provenance"
        ).fetchall()
        assert threshold_rows == [
            (170000000000000001, 170000000000000101, 1, 1, 1)
        ]

    assert len(fake_lasair.calls) == 1
    assert fake_lasair.calls[0]["objectId"] == "170000000000000001"
    assert fake_lasair.calls[0]["classification"] == "0.8"
    assert fake_lasair.calls[0]["classdict"]["stem"] == stem
