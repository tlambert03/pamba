import contextlib
import json
import os
import platform
import re
import shutil
import sys
from argparse import ArgumentParser, Namespace
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from subprocess import check_call
from typing import List, Optional, Sequence, Tuple, Union
from urllib import error, request

import toml
from build.util import project_wheel_metadata
from grayskull.strategy import pypi
from yaspin import yaspin


def _get_pep517_requires_dist(srcdir: Path) -> List[str]:
    meta = project_wheel_metadata(srcdir)
    return meta.get_all("Requires-Dist") or []


def _get_setuptools_requires_dist(srcdir: Path) -> List[str]:
    from setuptools.config.setupcfg import read_configuration

    cfg = read_configuration(str(srcdir / "setup.cfg"))
    requires: list = cfg["options"].get("install_requires") or []
    for extra, packages in cfg["options"].get("extras_require", {}):
        for pkg in packages:
            if ";" in pkg:
                requires.append(f"{pkg} and (extra == {extra!r})")
            else:
                requires.append(f"{pkg} ; extra == {extra!r}")
    return requires


def get_requires(srcdir: Union[str, Path]) -> List[str]:
    srcpath = Path(srcdir)
    assert srcpath.exists(), f"Path doesn't exist: {srcdir}"
    if (pyproject := srcpath / "pyproject.toml").exists():
        data = toml.load(pyproject)
        if "build-system" in data:
            return _get_pep517_requires_dist(srcpath)
    if (srcpath / "setup.cfg").exists():
        return _get_setuptools_requires_dist(srcpath)
    raise NotImplementedError("only PEP517 projects with pyproject.toml supported")


ENV = {
    "python_version": platform.python_version()[:3],
    "platform_version": platform.version(),
    "os_name": os.name,
    "sys_platform": sys.platform,
    "platform_release": platform.release(),
    "implementation_name": sys.implementation.name,
    "platform_machine": platform.machine(),
    "platform_python_implementation": platform.python_implementation(),
}


def clean_requires(requires: List[str], extras: Sequence[str] = ()) -> List[str]:
    reqs = []
    names = ENV.copy()
    for line in requires:
        dep, *rest = line.split(";")
        if rest:
            if "extra ==" in line:
                for extra in extras:
                    names["extra"] = extra
                    if eval(rest[0], names):
                        reqs.append(dep.strip())
            else:
                names.pop("extra", None)
                if eval(rest[0], names):
                    reqs.append(dep.strip())
        else:
            reqs.append(dep.strip())
    return reqs


def condafy_reqs(requires: List[str]) -> List[str]:
    """take a list of pip requires and return conda requires"""

    meta = {"name": "name", "requires_dist": requires}
    cfg = pypi.Configuration("n")

    all_reqs = pypi.extract_requirements(meta, cfg, None)
    run_req = pypi.solve_list_pkg_name(all_reqs["run"], pypi.PYPI_CONFIG)
    with contextlib.suppress(ValueError):
        run_req.remove("python")
    return pypi.ensure_pep440_in_req_list(run_req)  # type: ignore


def _normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name.split(" ")[0]).lower()


def _hit_conda_api(args: Tuple[str, Sequence[str]]) -> Tuple[Optional[str], str]:
    name, channels = args
    for channel in channels:
        url = f"https://api.anaconda.org/package/{channel}/{_normalized_name(name)}"
        with contextlib.suppress(error.HTTPError):
            with request.urlopen(url) as respose:
                if "error" not in json.load(respose):
                    return (channel, name)
    return (None, name)


def check_conda_availability(
    requires: List[str], channels: Sequence[str] = ("conda-forge",)
) -> Tuple[List[str], List[str]]:

    with ThreadPoolExecutor() as exec:
        results = exec.map(_hit_conda_api, [(r, channels) for r in requires])

    avail = []
    bad = []
    for chan, pkg in list(results):
        if chan:
            avail.append(pkg)
        else:
            bad.append(pkg)
    return avail, bad


def conda_install(requires: List[str], extra_args: Optional[List[str]] = None) -> None:
    if extra_args is None:
        extra_args = []
    if shutil.which("mamba"):
        binary = "mamba"
    elif shutil.which("conda"):
        binary = "conda"
    else:
        raise RuntimeError("Neither conda nor mamba available on PATH")
    check_call([binary, "install"] + extra_args + requires)


def pip_install(requires: List[str], extra_args: Optional[List[str]] = None) -> None:
    if extra_args is None:
        extra_args = []
    check_call(["pip", "install"] + extra_args + requires)


def install(args: Namespace, conda_args: Optional[List[str]] = None) -> None:
    extras = []
    requires = []
    pth = None
    if args.editable:
        _pth, _, _extras = str(args.editable[0]).partition("[")
        pth = Path(_pth).expanduser().absolute()
        extras = [x.strip() for x in _extras.rstrip("]").split(",") if x.strip()]
        with yaspin(text=f"Collecting requirements for {pth.name} ...", color="yellow"):
            requires = get_requires(pth)
    with yaspin(text="Converting requirements to conda ...", color="yellow"):
        requires.extend(args.requirements)
        requires = clean_requires(requires, extras)
        requires = condafy_reqs(requires)
    with yaspin(text="Checking conda availability ...", color="yellow"):
        from_conda, from_pip = check_conda_availability(requires)
    if args.dry_run:
        if from_conda:
            print("Would install from conda:")
            for req in from_conda:
                print(f"  - {req}")
        if from_pip:
            print("Would install from pip:")
            for req in from_conda:
                print(f"  - {req}")
    else:
        if from_conda:
            print("installing conda deps")
            conda_install(from_conda, extra_args=conda_args)
        if from_pip:
            print("installing remaining pip deps")
            pip_install([r.replace(" ", "") for r in from_pip])
        if args.editable and pth:
            print(f"installing {pth} in editable mode")
            pip_install([str(pth)], ["-e"])


def parse_args() -> None:
    parser = ArgumentParser(description="pamba installs pip requirements from conda")
    subs = parser.add_subparsers()
    _install = subs.add_parser("install")
    _install.add_argument("-e", "--editable", metavar="<local project path>", nargs=1)
    _install.add_argument("requirements", metavar="<requirement specifiers>", nargs="*")
    _install.add_argument(
        "-n", "--dry-run", action="store_true", help="dont install anything"
    )
    _install.set_defaults(func=install)
    args, conda_args = parser.parse_known_args()
    if hasattr(args, "func"):
        args.func(args, conda_args)
    else:
        parser.print_help()


def main() -> None:
    parse_args()
