import git
import json
import argparse
import os
import tomllib
from tempfile import TemporaryDirectory
import subprocess

from workflow_miner import parse_test_failures


class FlakinessReproducer:
    def __init__(self, local_repo_path: str):
        self.local_repo = git.Repo(local_repo_path)

    def reproduce_flakiness(self, sha: str, tests_to_check: list, repeats: int = 100):
        self.local_repo.git.reset("--hard")
        self.local_repo.git.fetch("origin", sha)
        self.local_repo.git.checkout(sha)
        results = {}
        with TemporaryDirectory() as worktree_path:
            self.local_repo.git.worktree("add", worktree_path, sha)
            for test in tests_to_check:
                passes = 0
                failures = 0
                for _ in range(repeats):
                    # TODO: Need to work out how to make sure everything is setup/installed correctly
                    result = subprocess.run(
                        ["uv", "run", "--isolated", "python", "-m", "pytest", test],
                        cwd=worktree_path,
                        check=False,
                        capture_output=True,
                        text=True,
                    )
                    print("STDOUT", result.stdout)
                    print("STDERR", result.stderr)
                    failed_tests = parse_test_failures(result.stdout)
                    failures += test in failed_tests
                    passes += test not in failed_tests
                    if passes and failures:
                        break
                results[test] = {"passes": passes, "failures": failures}
        self.local_repo.git.reset("--hard")


def main():
    parser = argparse.ArgumentParser(
        prog="reproduce_flakiness", description="Attempt to reproduce the flaky tests from a given repo."
    )

    parser.add_argument(
        "-j", "--json-file", help="The location of the JSON file containing the test data.", required=True
    )
    parser.add_argument("-r", "--local-repo-path", help="Location of the repo.")
    parser.add_argument(
        "-m", "--max-repeats", help="Maximum number of repeats to run when looking for flaky behaviour."
    )

    args = parser.parse_args()
    with open(args.json_file) as f:
        runs = json.load(f)

    flakiness_reproducer = FlakinessReproducer(args.local_repo_path)

    for run in runs:
        print(run["run_id"])
        flakiness_reproducer.reproduce_flakiness(
            run["pull_request"]["target_sha"], [t["test_id"] for t in run["failed_tests"]]
        )


if __name__ == "__main__":
    main()
