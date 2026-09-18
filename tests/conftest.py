import helpers

import pytest


@pytest.fixture
def config():
    return helpers.make_config()
