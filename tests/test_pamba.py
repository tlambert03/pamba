from typing import Iterable
import pytest
from pamba.env import IsolatedEnvBuilder, _IsolatedEnvConda
from pamba.cli import install


@pytest.fixture(scope="session")
def isolated_conda_env() -> Iterable[_IsolatedEnvConda]:
    with IsolatedEnvBuilder(conda=True) as env:
        yield env


def test_something(isolated_conda_env: _IsolatedEnvConda):
    install(["PyQt5"], _conda_install=isolated_conda_env.install)
    assert True  # TODO
