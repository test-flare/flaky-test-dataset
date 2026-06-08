import json
import argparse
from multiprocessing import Pool
import docker
from tqdm import tqdm

from workflow_miner import parse_test_failures


class FlakinessReplicator:
    """
    Class to manage the replication of flaky test behaviour.
    """

    def __init__(self, container_name: str):
        self.container_name = container_name

    def run_command(self, container: docker.models.containers.Container, command: str) -> str:
        """
        Run the supplied command on the docker client, check for success, and return the output logs.
        :param container: The docker container.
        :param command: The command to run.
        :returns: The console output of the command.
        """
        exit_code, logs = container.exec_run(command)
        logs = logs.decode("utf-8")

        if exit_code != 0:
            raise ValueError(f"Container failed with exit code {exit_code}" + (logs if logs else "No logs captured."))
        return logs

    def replicate_flakiness(self, sha: str, tests_to_check: list[str], repeats: int = 2) -> dict:
        """
        Attempt to replicate the flaky behaviour of a given set of tests by repeatedly running them and looking for
        different outcomes.
        :param sha: The git sha of the commit to observe.
        :param tests_to_check: The pytest IDs of the tests to run.
        :param repeats: The maximum number of times to execute each test.
        :return: Dictionary of the number of `passes` and `failures` for each test case.
        """
        client = docker.from_env()
        container = client.containers.run(self.container_name, entrypoint="bash", detach=True, tty=True)

        results = {test: {"passes": 0, "failures": 0} for test in tests_to_check}

        try:
            logs = self.run_command(container, f"sh ./setup.sh {sha}")
            print(logs)

            for _ in tqdm(range(repeats)):
                logs = self.run_command(container, f"bash ./test.sh {' '.join(tests_to_check)}")

                failed_tests = parse_test_failures(logs)
                for test in tests_to_check:
                    results[test]["failures"] += test in failed_tests
                    results[test]["passes"] += test not in failed_tests
                if all(results[test]["failures"] and results[test]["passes"] for test in tests_to_check):
                    break
            return results
        finally:
            container.stop()
            container.remove()


def get_args():
    parser = argparse.ArgumentParser(
        prog="replicate_flakiness", description="Attempt to replicate the flaky tests from a given repo."
    )

    parser.add_argument(
        "-j", "--input-json", help="The location of the JSON file containing the test data.", required=True
    )
    parser.add_argument("-c", "--container-name", help="Name of the docker container.", required=True)
    parser.add_argument("-r", "--run-id", help="ID of the run to replicate.")
    parser.add_argument(
        "-o", "--output-json", help="Where to save the output. Defaults to overwriting the input JSON data."
    )
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
    if not args.output_json:
        args.output_json = args.input_json
    return args


def main():
    """
    Main entrypoint for flakiness replication.
    """
    args = get_args()
    with open(args.input_json) as f:
        runs = json.load(f)
    if args.run_id:
        runs = [run for run in runs if run["run_id"] == args.run_id]

    flakiness_replicator = FlakinessReplicator(container_name=args.container_name)

    if args.threads is not None:
        with Pool(args.threads) as pool:
            flakiness = pool.starmap(
                flakiness_replicator.replicate_flakiness,
                [(run["pull_request"]["source_sha"], list(run["failed_tests"])) for run in runs],
            )
        for run, flaky in zip(runs, flakiness):
            run["failed_tests"] = {
                test_id: metadata | flaky[test_id] for test_id, metadata in runs["failed_tests"].items()
            }
        with open(args.json_file, "w") as f:
            json.dump(runs, f, indent=2)
    else:
        for run in runs:
            print(run["pull_request"]["source_sha"])
            flaky = flakiness_replicator.replicate_flakiness(run["pull_request"]["source_sha"], run["failed_tests"])
            run["failed_tests"] = {
                test_id: metadata | flaky[test_id] for test_id, metadata in run["failed_tests"].items()
            }
        with open(args.json_file, "w") as f:
            json.dump(runs, f, indent=2)


if __name__ == "__main__":
    main()
