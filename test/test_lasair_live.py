
"""
Not run in CI - Just by hand by me. To run it do: pytest -m live test_lasair_live.py 
Oversight: High
"""
# Claude wrote this for the Lasair API-only server hotfix (2026-11-13)
import os
from datetime import datetime, timezone
from pathlib import Path

import lasair
import pytest
import yaml

pytestmark = pytest.mark.live

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
# This is some random "NT" that looks like bogus that I found my looking at the Lasair front page
# I don't think it'll ever become a relevant LVRA target so I'm using it for my etests
TEST_OBJECT_ID = 313888627151077520


def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="module")
def client():
    token = os.getenv("LASAIR_LSST_TOKEN")
    assert token, "LASAIR_LSST_TOKEN not set"
    settings = load_yaml(os.getenv("LVRA_SETTINGS", DATA_DIR / "public_settings.yaml"))
    print(f"endpoint: {settings['endpoint']}")
    return lasair.lasair_client(token, endpoint=settings['endpoint'])


def test_smoke_object_read(client):
    result = client.object(TEST_OBJECT_ID, lite=True, lasair_added=True)
    assert int(result['diaObjectId']) == TEST_OBJECT_ID


@pytest.mark.parametrize("config_file", ["r0b_config.yaml", "lvra_config.yaml"])
def test_annotate_roundtrip(client, config_file):
    config = load_yaml(DATA_DIR / config_file)
    # version must be 16 chars or less 
    version = f"smoket_{datetime.now(timezone.utc):%Y%m%dT}"
    client.annotate(topic=config['TOPIC_OUT'],
                    objectId=TEST_OBJECT_ID,
                    classification="smoketest",
                    version=version,
                    explanation="Smoke test of the Lasair API endpoint, not a real classification",
                    classdict={},
                    url=config['URL'])

    annotations = client.object(TEST_OBJECT_ID, lite=True, lasair_added=True)['lasairData']['annotations']
    ours = [a for a in annotations if a['topic'] == config['TOPIC_OUT']]
    print(ours)
    assert any(a['version'] == version for a in ours)
