import json
import os
import socket as _socket

import pytest

HERE = os.path.dirname(__file__)
PROFILE = os.path.join(HERE, "golden", "profiles", "young_saver_TX.json")


@pytest.fixture
def profile():
    with open(PROFILE, "r", encoding="utf-8") as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
# Network fence (P0-CI): no test may make a live external network call.
# This keeps the LLM stubbed (never live Gemini) and CI hermetic. Connections
# to localhost are allowed so future tests can drive a local web/app.py.
# --------------------------------------------------------------------------- #
_LOCAL_HOSTS = {"127.0.0.1", "::1", "localhost", ""}


def _host_of(address):
    if isinstance(address, (tuple, list)) and address:
        return address[0]
    return address


@pytest.fixture(autouse=True, scope="session")
def _block_external_network():
    real_connect = _socket.socket.connect
    real_create = _socket.create_connection

    def guarded_connect(self, address, *args, **kwargs):
        if _host_of(address) not in _LOCAL_HOSTS:
            raise RuntimeError(
                f"External network call blocked in tests: {address!r}. "
                "Stub the LLM/HTTP instead of calling out (see tests/test_agents.py)."
            )
        return real_connect(self, address, *args, **kwargs)

    def guarded_create(address, *args, **kwargs):
        if _host_of(address) not in _LOCAL_HOSTS:
            raise RuntimeError(f"External network call blocked in tests: {address!r}.")
        return real_create(address, *args, **kwargs)

    _socket.socket.connect = guarded_connect
    _socket.create_connection = guarded_create
    try:
        yield
    finally:
        _socket.socket.connect = real_connect
        _socket.create_connection = real_create
