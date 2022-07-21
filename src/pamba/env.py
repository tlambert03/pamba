from typing import Callable, Collection, List, Optional
import build
import build.env
import tempfile
import os
import sys
import subprocess

CONDA_BIN = "mamba"  # TODO

import site
site.getsitepackages
def _subprocess(cmd: List[str]) -> None:
    """Invoke subprocess and output stdout and stderr if it fails."""
    try:
        # stdout=subprocess.PIPE, stderr=subprocess.STDOUT

        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(e.output.decode(), end="", file=sys.stderr)
        raise e


class IsolatedEnvBuilder(build.env.IsolatedEnvBuilder):
    """Builder object for isolated environments."""

    def __init__(self, conda: bool = True) -> None:
        self._path: Optional[str] = None
        self._conda = conda

    def __enter__(self) -> build.env.IsolatedEnv:
        if self._conda:
            self._path = os.path.realpath(tempfile.mkdtemp(prefix="build-env-"))
            _create_isolated_env_conda(self._path)
            return _IsolatedEnvConda(prefix=self._path, log=self.log)
        return super().__enter__()


def _create_isolated_env_conda(
    path: str, conda_bin: str = CONDA_BIN, pyver: str = ""
) -> None:
    if not pyver:
        pyver = ".".join(map(str, sys.version_info[:3]))

    _subprocess([conda_bin, "create", "-p", path, "-y", f"python=={pyver}"])


class _IsolatedEnvConda(build.env.IsolatedEnv):
    def __init__(
        self,
        prefix: str,
        log: Callable[[str], None],
        conda_bin: str = CONDA_BIN,
    ) -> None:
        self._prefix = prefix
        self._conda_bin = conda_bin
        self._log = log

    @property
    def path(self) -> str:
        """The location of the isolated build environment."""
        return self._prefix

    @property
    def executable(self) -> str:
        """The python executable of the isolated build environment."""
        return os.path.join(self.scripts_dir, "python")

    @property
    def scripts_dir(self) -> str:
        return os.path.join(self._prefix, "bin")

    def install(self, requirements: Collection[str], extra_args=None) -> None:
        if not requirements:
            return

        self._log(
            "Installing packages in isolated environment... "
            f'({", ".join(sorted(requirements))})'
        )

        cmd = [self._conda_bin, "install", "-p", self.path] + list(requirements)
        _subprocess(cmd)
