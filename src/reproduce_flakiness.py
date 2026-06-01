import json
import argparse
from multiprocessing import Pool
import docker
from tqdm import tqdm

from workflow_miner import parse_test_failures


class FlakinessReproducer:
    """
    Class to manage the replication of flaky test behaviour.
    """

    def __init__(self, container_name: str):
        self.container_name = container_name

    def run_command(self, client: docker.client.DockerClient, command: str) -> str:
        """
        Run the supplied command on the docker client, check for success, and return the output logs.
        :param client: The docker client.
        :param command: The command to run.
        :returns: The console output of the command.
        """
        container = client.containers.run(self.container_name, entrypoint="bash", detach=True, tty=True)
        try:
            exit_code, logs = container.exec_run(command)
            logs = logs.decode("utf-8")

            if exit_code != 0:
                raise ValueError(
                    f"Container failed with exit code {exit_code}" + (logs if logs else "No logs captured.")
                )
        finally:
            container.stop()
            container.remove()
        return logs

    def reproduce_flakiness(self, sha: str, tests_to_check: list[str], repeats: int = 2) -> dict:
        """
        Attempt to reproduce the flaky behaviour of a given set of tests by repeatedly running them and looking for
        different outcomes.
        :param sha: The git sha of the commit to observe.
        :param tests_to_check: The pytest IDs of the tests to run.
        :param repeats: The maximum number of times to execute each test.
        :return: Dictionary of the number of `passes` and `failures` for each test case.
        """
        client = docker.from_env()
        results = {test: {"passes": 0, "failures": 0} for test in tests_to_check}
        self.run_command(client, f"bash ./setup.sh {sha}")

        for _ in tqdm(range(repeats)):
            logs = self.run_command(client, f"bash ./setup.sh {' '.join(tests_to_check)}")

            failed_tests = parse_test_failures(logs)
            for test in tests_to_check:
                results[test]["failures"] += test in failed_tests
                results[test]["passes"] += test not in failed_tests
            if all(results[test]["failures"] and results[test]["passes"] for test in tests_to_check):
                break
        return results


def main():
    """
    Main entrypoint for flakiness replication.
    """
    parser = argparse.ArgumentParser(
        prog="reproduce_flakiness", description="Attempt to reproduce the flaky tests from a given repo."
    )

    parser.add_argument(
        "-j", "--json-file", help="The location of the JSON file containing the test data.", required=True
    )
    parser.add_argument("-c", "--container-name", help="Name of the docker container.")
    parser.add_argument(
        "-m", "--max-repeats", type=int, help="Maximum number of repeats to run when looking for flaky behaviour."
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        help="Number of threads to run in parallel. Defaults to 1 (i.e. serial).",
        default=None,
    )

    args = parser.parse_args()
    with open(args.json_file) as f:
        runs = json.load(f)

    flakiness_reproducer = FlakinessReproducer(container_name=args.container_name)

    if args.threads is not None:
        with Pool(args.threads) as pool:
            pool.starmap(
                flakiness_reproducer.reproduce_flakiness,
                [(run["pull_request"]["target_sha"], [t["test_id"] for t in run["failed_tests"]]) for run in runs],
            )
    else:
        for run in runs:
            run["flakiness"] = flakiness_reproducer.reproduce_flakiness(
                run["pull_request"]["target_sha"], [t["test_id"] for t in run["failed_tests"]]
            )
    with open(args.json_file, "w") as f:
        json.dump(runs, f, indent=2)


if __name__ == "__main__":
    main()
