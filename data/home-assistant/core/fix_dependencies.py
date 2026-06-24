import os
from glob import glob
import re

REPO_PATH = "core"


def fix_dependencies():
    """
    Apply workarounds for missing dependencies.
    """
    replacements = {
        r"mypy\-dev==\d+\.\d+\.\w+": "mypy-dev",
        r"aioasuswrt==1\.5\.1": "aioasuswrt==1.5.2",
        # No longer availble in any form, but not necessary for the tests we need to run so we comment it out
        "pyunifiprotect": "#pyunifiprotect",
        "pymazda": "#pymazda",
        "urllib3>=1.26.5": "urllib3<1.27,>=1.21.1",
        # Conflicting sub-dependencies (not required for testing)
        "ibm-watson": "#ibm-watson",
        "mycroftapi": "#mycroftapi",
        "pysmarty": "#pysmarty",
        "pytradfri": "#pytradfri",
        "pycocotools": "#pycocotools",
    }
    package_constraints = os.path.join(REPO_PATH, "homeassistant/package_constraints.txt")
    constraints = set()
    for fname in glob(os.path.join(REPO_PATH, "*requirements*.txt"), recursive=True) + [package_constraints]:
        with open(fname) as f:
            packages = f.readlines()
        for old, new in replacements.items():
            packages = [re.sub(old, new, p) for p in packages]
        if any("aiodns==3" in line for line in packages):
            # aiodns depends on pycares, but is not sufficiently strict on versioning:
            # pycares 5+ is not compatible with python 3.14
            constraints.add("pycares<5")
        if any("hass-nabucasa==0.8" in line for line in packages):
            # module 'josepy' has no attribute 'ComparableX509'
            constraints.add("josepy<2")
        if any("requests==2.28.1" in line for line in packages):
            # requests 2.28.1 requires urllib3<1.27,>=1.21.1
            constraints.add("urllib3<1.27,>=1.21.1")
        with open(fname, "w") as f:
            f.write("\n".join(packages))
        with open(package_constraints, "a") as f:
            for constraint in constraints:
                f.write(constraint + "\n")


def configure_pyproject():
    """
    Add the flakefighters config to the pyproject.toml file
    """
    with open(os.path.join(REPO_PATH, "pyproject.toml"), "a") as f:
        f.write(
            """
        [tool.pytest.ini_options.pytest_flakefighters.flakefighters.diffcov.DiffCov]
        run_live=false

        [tool.pytest.ini_options.pytest_flakefighters.flakefighters.traceback_matching.TracebackMatching]
        run_live=false

        [tool.pytest.ini_options.pytest_flakefighters.flakefighters.traceback_matching.CosineSimilarity]
        run_live=false

        [tool.pytest.ini_options.pytest_flakefighters.flakefighters.coverage_independence.CoverageIndependence]
        run_live=false
        """
        )


if __name__ == "__main__":
    fix_dependencies()
    configure_pyproject()
