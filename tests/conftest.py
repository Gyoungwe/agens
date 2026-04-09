# tests/conftest.py

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def anyio_backend():
    return "asyncio"
