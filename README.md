# pamba

[![License](https://img.shields.io/pypi/l/pamba.svg?color=green)](https://github.com/tlambert03/pamba/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/pamba.svg?color=green)](https://pypi.org/project/pamba)
[![Python Version](https://img.shields.io/pypi/pyversions/pamba.svg?color=green)](https://python.org)
[![CI](https://github.com/tlambert03/pamba/actions/workflows/ci.yml/badge.svg)](https://github.com/tlambert03/pamba/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/tlambert03/pamba/branch/main/graph/badge.svg)](https://codecov.io/gh/tlambert03/pamba)

Installl pyproject/setup.cfg deps from mamba

for now ...

```sh
pip install git+https://github.com/tlambert03/pamba.git
```

install local path in pip editable mode, but install dependencies with mamba/conda

```sh
pamba install -e '~/local/path[extraA,extraB]'
```

convert pypi package names to conda names and install with mamba/conda

```sh
pamba install packageA packageB
```
