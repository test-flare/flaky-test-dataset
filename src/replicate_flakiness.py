import json
import argparse
from multiprocessing import Pool
import docker
import os
from tqdm import tqdm
import datetime

from workflow_miner import parse_failure_logs

BASE_DIR = "data"


class FlakinessReplicator:
    """
    Class to manage the replication of flaky test behaviour.
    """

    def __init__(self, repo_owner: str, repo_name: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name

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

    def replicate_flakiness(
        self, sha: str, tests_to_check: list[str], repeats: int = 2, terminate_early: bool = False
    ) -> dict:
        """
        Attempt to replicate the flaky behaviour of a given set of tests by repeatedly running them and looking for
        different outcomes.
        :param sha: The git sha of the commit to observe.
        :param tests_to_check: The pytest IDs of the tests to run.
        :param repeats: The maximum number of times to execute each test.
        :param terminate_early: Terminate repeated test execution as soon as one pass and one failure have been
                                observed.
        :return: Dictionary of the number of `passes` and `failures` for each test case.
        """
        client = docker.from_env()
        image, _ = client.images.build(
            path=os.path.join(BASE_DIR, self.repo_owner, self.repo_name),
            # tag=f"{self.repo_owner.lower()}:{self.repo_name.lower()}",
            rm=True,  # Remove intermediate containers after a successful build
        )
        container = client.containers.run(image, entrypoint="bash", detach=True, tty=True)

        results = {test: {"passes": 0, "failures": 0, "failure_logs": []} for test in tests_to_check}

        try:
            logs = self.run_command(container, f"sh ./setup.sh {sha}")
            print(logs)

            for _ in tqdm(range(repeats)):
                logs = self.run_command(container, f"bash ./test.sh {' '.join(tests_to_check)}")

                failed_tests = parse_failure_logs(logs)
                with open("/tmp/failurelog.txt", "w") as f:
                    f.write(logs)
                for test in tests_to_check:
                    results[test]["failures"] += test in failed_tests
                    results[test]["passes"] += test not in failed_tests
                    if test in failed_tests:
                        results[test]["failure_logs"].append(failed_tests.get(test, {}).get("github_log", ""))
                if (
                    all(results[test]["failures"] and results[test]["passes"] for test in tests_to_check)
                    and terminate_early
                ):
                    break
            return results
        finally:
            container.stop()
            container.remove()


def get_args() -> argparse.Namespace:
    """
    Parse commandline arguments.
    :returns: Namespace containing the supplied arguments.
    """
    parser = argparse.ArgumentParser(
        prog="replicate_flakiness", description="Attempt to replicate the flaky tests from a given repo."
    )

    parser.add_argument("-r", "--run-ids", help="IDs of the run to replicate.", type=int, nargs="+")
    parser.add_argument("-o", "--repo-owner", help="The name of the repo owner.", required=True)
    parser.add_argument("-n", "--repo-name", help="The name of the repo.", required=True)
    parser.add_argument("-b", "--branch-name", help="The name of the branch.", required=True)
    parser.add_argument(
        "-g",
        "--generate-template-scripts",
        help="Use this to generate a template dockerfile and run scripts.",
        action="store_true",
    )
    parser.add_argument(
        "-O",
        "--output-json",
        help=(
            "Where to save the output. Defaults to `data/${repo_owner}/${repo_name}/${branch_name}-${timestamp}.json` "
            "so as not to overwrite data."
        ),
    )
    parser.add_argument(
        "-I",
        "--input-json",
        help="Where to find the run data. Defaults to  `data/${repo_owner}/${repo_name}/${branch_name}.json`.",
    )
    parser.add_argument(
        "-m",
        "--max-repeats",
        type=int,
        default=2,
        help="Maximum number of repeats to run when looking for flaky behaviour.",
    )
    parser.add_argument(
        "-t",
        "--threads",
        type=int,
        help="Number of threads to run in parallel. Defaults to 1 (i.e. serial).",
        default=None,
    )
    parser.add_argument(
        "-R",
        "--running-total",
        action="store_true",
        help=(
            "Set to add to the current recorded test run statistics rather than overwriting."
            "For example, if a test has already passed 20 times and failed 30 times and 10 more repeats are run, "
            "the outcomes will be added to these values if this flag is set."
        ),
        default=None,
    )
    parser.add_argument(
        "-T",
        "--terminate-early",
        action="store_true",
        help=(
            "Terminate as soon as one passing and one failing run has been observed, otherwise run the specified "
            "`--max-repeats` and record the outcome each time."
        ),
        default=None,
    )

    args = parser.parse_args()
    if not args.input_json:
        args.input_json = os.path.join(BASE_DIR, args.repo_owner, args.repo_name, f"{args.branch_name}.json")
    if not args.output_json:
        args.output_json = args.input_json.replace(".json", datetime.datetime.now().isoformat() + ".json")
    return args


def generate_template_scripts(repo_owner, repo_name):
    project_directory = os.path.join(BASE_DIR, repo_owner, repo_name)
    os.makedirs(project_directory, exist_ok=True)
    with open(os.path.join(project_directory, "setup.sh"), "w") as f:
        f.write(
            f"""#!/bin/bash
cd {repo_name}
git reset --hard
git fetch origin $1
git checkout $1

# Commands to set up and install the repo
python -m uv sync --group dev
        """
        )
    with open(os.path.join(project_directory, "test.sh"), "w") as f:
        f.write(
            f"""#!/bin/bash
cd {repo_name}
.venv/bin/python -m uv run pytest "$@"

# Check the exit code
# Exit code 0: All tests were collected and passed successfully
# Exit code 1: Tests were collected and run but some of the tests failed
# Exit code 2: Test execution was interrupted by the user
# Exit code 3: Internal error happened while executing tests
# Exit code 4: pytest command line usage error
# Exit code 5: No tests were collected

# We want the exit code to be 0 even if tests failed, since this is expected here.
# We only want a non-zero exit code if there is a problem running pytest itself, as this will interupt
# the docker container.
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ] || [ $EXIT_CODE -eq 1 ]; then
    exit 0
else
    exit $EXIT_CODE
fi
        """
        )
    with open(os.path.join(project_directory, "Dockerfile"), "w") as f:
        f.write(
            f"""# You may need to change the python version
FROM python:3.13-bookworm

RUN addgroup --gid 1002 "flakehunter" && \\
    adduser --disabled-password --gecos "FlakeFighters User,,," \\
    --home /home/flakehunter --ingroup flakehunter --uid 1002 flakehunter

# Set working directory
WORKDIR /home/flakehunter

# Install system dependencies
RUN apt-get update && apt-get install -y \\
    bash \\
    git \\
    && rm -rf /var/lib/apt/lists/*


USER 1002:1002


# Clone the repo and set up config with dummy details
RUN git clone https://github.com/{repo_owner}/{repo_name}.git; \\
    git config --global user.email "you@example.com"; \\
    git config --global user.name "Your Name"

# Install pytest and the flake-fighting plugin
RUN pip install --no-cache-dir uv pytest pytest-flakefighters

# Copy the scripts
COPY --chown=1002:1002 setup.sh setup.sh
COPY --chown=1002:1002 test.sh test.sh
RUN chmod +x setup.sh test.sh
        """
        )


def main():
    """
    Main entrypoint for flakiness replication.
    """
    args = get_args()
    if args.generate_template_scripts:
        generate_template_scripts(args.repo_owner, args.repo_name)
        return
    with open(args.input_json) as f:
        runs = json.load(f)
    if args.run_ids:
        matching_runs = [run for run in runs if run["run_id"] in args.run_ids]
        failed_ids = set(args.run_ids) - set(map(lambda run: run["run_id"], matching_runs))
        if failed_ids:
            raise ValueError(f"No run found with id {failed_ids}.")
    else:
        matching_runs = runs

    flakiness_replicator = FlakinessReplicator(repo_owner=args.repo_owner, repo_name=args.repo_name)

    if args.threads is not None:
        with Pool(args.threads) as pool:
            flakiness = pool.starmap(
                flakiness_replicator.replicate_flakiness,
                [
                    (
                        run["pull_request"]["source_sha"],
                        list(run["failed_tests"]),
                        args.max_repeats,
                        args.terminate_early,
                    )
                    for run in matching_runs
                ],
            )
        for run, flaky in zip(matching_runs, flakiness):
            run["failed_tests"] = {
                test_id: metadata | flaky[test_id] for test_id, metadata in run["failed_tests"].items()
            }
        with open(args.output_json, "w") as f:
            json.dump(runs, f, indent=2)
    else:
        for run in matching_runs:
            print(run["pull_request"]["source_sha"])
            flaky = flakiness_replicator.replicate_flakiness(
                run["pull_request"]["source_sha"],
                run["failed_tests"],
                repeats=args.max_repeats,
                terminate_early=args.terminate_early,
            )
            if args.running_total:
                for test_id, metadata in run["failed_tests"].items():
                    run["failed_tests"][test_id]["passed"] += metadata["passed"] + (
                        run["failed_tests"][test_id].get("passed", 0)
                    )
                    run["failed_tests"][test_id]["failed"] += metadata["failed"] + (
                        run["failed_tests"][test_id].get("failed", 0)
                    )

            else:
                run["failed_tests"] = {
                    test_id: metadata | flaky[test_id] for test_id, metadata in run["failed_tests"].items()
                }
        with open(args.output_json, "w") as f:
            json.dump(runs, f, indent=2)


if __name__ == "__main__":
    main()
