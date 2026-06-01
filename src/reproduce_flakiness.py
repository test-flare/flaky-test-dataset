import git
import json
import argparse
import os
import tomllib
from tempfile import TemporaryDirectory
import subprocess
import docker
from tqdm import tqdm

from workflow_miner import parse_test_failures


class FlakinessReproducer:
    def __init__(self, container_name: str):
        self.container_name = container_name
        self.client = docker.from_env()

    def run_command(self, cmd: str):
        container = self.client.containers.run(self.container_name, entrypoint="bash", detach=True, tty=True)
        try:
            exit_code, logs = container.exec_run(cmd)
            logs = logs.decode("utf-8")

            if exit_code != 0:
                raise ValueError(
                    f"Container failed with exit code {exit_code}" + (logs if logs else "No logs captured.")
                )
        finally:
            container.stop()
            container.remove()
        return logs

    def reproduce_flakiness(self, sha: str, tests_to_check: list, repeats: int = 2):
        results = {test: {"passes": 0, "failures": 0} for test in tests_to_check}
        self.run_command(f"bash ./setup.sh {sha}")

        for _ in tqdm(range(repeats)):
            logs = self.run_command(f"bash ./setup.sh {' '.join(tests_to_check)}")

            failed_tests = parse_test_failures(logs)
            for test in tests_to_check:
                results[test]["failures"] += test in failed_tests
                results[test]["passes"] += test not in failed_tests
            if all(results[test]["failures"] and results[test]["passes"] for test in tests_to_check):
                break
        return results


def main():
    parser = argparse.ArgumentParser(
        prog="reproduce_flakiness", description="Attempt to reproduce the flaky tests from a given repo."
    )

    parser.add_argument(
        "-j", "--json-file", help="The location of the JSON file containing the test data.", required=True
    )
    parser.add_argument("-c", "--container-name", help="Name of the docker container.")
    parser.add_argument(
        "-m", "--max-repeats", help="Maximum number of repeats to run when looking for flaky behaviour."
    )

    args = parser.parse_args()
    with open(args.json_file) as f:
        runs = json.load(f)

    flakiness_reproducer = FlakinessReproducer(container_name=args.container_name)

    for run in runs:
        print(run["run_id"])
        run["flakiness"] = flakiness_reproducer.reproduce_flakiness(
            run["pull_request"]["target_sha"], [t["test_id"] for t in run["failed_tests"]]
        )
        with open(args.json_file, "w") as f:
            json.dump(runs, f, indent=2)


if __name__ == "__main__":
    main()
