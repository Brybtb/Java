import json
import os

import pytest

HERE = os.path.dirname(__file__)
PROFILE = os.path.join(HERE, "golden", "profiles", "young_saver_TX.json")


@pytest.fixture
def profile():
    with open(PROFILE, "r", encoding="utf-8") as f:
        return json.load(f)
