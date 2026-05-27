"""
This module uses the  GitHub API to look for actions that were run, failed, rerun, and passed.
Results are saved to JSON in the specified location.
"""

import io
import json
import os
import tomllib
import zipfile
from tempfile import TemporaryDirectory
from tqdm import tqdm
import argparse
import re
from multiprocessing import Pool

import git
import requests
from dotenv import load_dotenv
from github import Auth, Github, Repository
from datetime import datetime, timedelta

load_dotenv()


def parse_test_failures(log: str) -> list[str]:
    """
    Parse the names of failed tests from the pytest log.
    :param log: The pytest log content.
    :returns: A list of the identifiers of the failed tests.
    """
    failed_tests = []
    # Pytest failure pattern in logs: FAILED path/to/test.py::test_name
    pytest_fail_regex = re.compile(r"(FAILED|ERROR|FLAKY)\s+([\w\/\.\d_]+::[\w\d_]+)")
    matches = pytest_fail_regex.findall(log)
    for m in matches:
        if m not in failed_tests:
            failed_tests.append(m[-1])
    return failed_tests


def get_failed_tests_from_logs(zip_content: str):
    """
    Take the zip output and parse test failures from the log.
    :param zip_content: The content of the zip file.
    """
    failed_tests = []

    with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
        for filename in z.namelist():
            with z.open(filename) as f:
                content = f.read().decode("utf-8", errors="ignore")
                failed_tests += parse_test_failures(content)
    return failed_tests


class RepoMiner:
    def __init__(
        self,
        github_token: str,
        repo_owner: str,
        repo_name: str,
        local_repo_path: str,
        base_branch: str,
        workflow_name: str,
        max_runs: int = 50,
    ):
        self.github_token = github_token
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.local_repo = git.Repo(local_repo_path)
        self.base_branch = base_branch
        self.workflow_name = workflow_name
        self.max_runs = max_runs

        self.local_repo.git.checkout(self.base_branch)
        self.local_repo.git.fetch()

    def requires_python(self, sha: str):
        """
        Returns the required python version string (if found) for a given commit sha.
        :param sha: The commit sha.
        """

        with TemporaryDirectory() as worktree_path:
            self.local_repo.git.worktree("add", worktree_path, sha)
            if os.path.exists(f"{worktree_path}/.python_version"):
                with open(f"{worktree_path}/.python_version") as f:
                    return "\n".join(f.readlines()).strip()
            if os.path.exists(f"{worktree_path}/pyproject.toml"):
                with open(f"{worktree_path}/pyproject.toml", "rb") as f:
                    return tomllib.load(f).get("project", {}).get("requires-python", "")
        return ""

    def get_test_metadata(
        self,
        test_id: str,
    ) -> dict:
        """
        Finds the commit that introduced a test.

        :param test_id: The full identifier of the test,
                        e.g. "tests/components/bang_olufsen/test_event.py::test_button_event_creation_a5".
        """
        # Find the commit that introduced the test function definition
        try:
            file_path, test_name = test_id.split("::")

            log_output = self.local_repo.git.log(
                f"-L:{test_name}:{file_path}", "--reverse", "--format=%H", "--no-patch"
            )
            introduction_commit_sha = log_output.strip().split("\n")[0]
            introduction_date = self.local_repo.commit(introduction_commit_sha).committed_datetime.isoformat()

            return {
                "introduced_in": introduction_commit_sha,
                "introduction_date": introduction_date,
            }

        except git.exc.GitCommandError as e:
            print(e)
            return None

    def get_run_metadata(self, remote: Repository, run: dict) -> dict:
        """
        Finds the commit hashes associated with the run, and identifies flaky test candidates.

        :param remote: The GitHub Repository.
        :param run: The workflow run.
        """
        log_url = (
            f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/actions/runs/{run['id']}/attempts/1/logs"
        )
        headers = {"Authorization": f"token {self.github_token}"}

        response = requests.get(log_url, headers=headers, timeout=30)
        pulls = remote.get_commit(run["head_sha"]).get_pulls()

        print(f"RUN: {run['id']} {run['event']} {response.status_code} {pulls.totalCount}")
        os.makedirs(f"runs/{run['id']}", exist_ok=True)
        with open(f"runs/{run['id']}/{run['id']}.zip", "wb") as f:
            f.write(response.content)

        if response.status_code == 200 and pulls.totalCount > 0:
            pr = pulls[0]
            failed_tests = []
            for test_id in get_failed_tests_from_logs(response.content):
                test_metadata = self.get_test_metadata(test_id)
                print(f"  {test_id}: {test_metadata}")
                if test_metadata:
                    failed_tests.append({"test_id": test_id} | test_metadata)
            print(f"  {len(failed_tests)} failed tests")

            if failed_tests:
                return {
                    "run_id": run["id"],
                    "run_attempt": run["run_attempt"],
                    "created_at": run["created_at"],
                    "failed_tests": failed_tests,
                    "pull_request": {
                        "number": pr.number,
                        "title": pr.title,
                        "created_at": pr.created_at.isoformat(),
                        # The Merge Commit created by GitHub for the CI run
                        "merge_sha": run["head_sha"],
                        # The Source (Feature Branch) commit
                        "source_sha": pr.head.sha,
                        # The Target (Base Branch, e.g., dev) commit
                        "target_sha": pr.base.sha,
                    },
                }
        return None

    def scrape_repo(self):
        """
        Main entrypoint. Scrape the repo and save the result to JSON.
        """
        output_dir = os.path.join("data", self.repo_owner, self.repo_name)
        output_file = os.path.join(output_dir, f"{self.base_branch}.json")
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        remote = Github(auth=Auth.Token(self.github_token)).get_repo(f"{self.repo_owner}/{self.repo_name}")
        found_count = 0

        data = []
        if os.path.exists(output_file):
            with open(output_file) as f:
                data = json.load(f)

        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/actions/runs"
        # Github only keeps run logs for a maximum of 90 days for public repos
        date_90_days_ago = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        params = {
            # "state": "closed",
            "status": "completed",
            "event": "pull_request",
            "conclusion": "success",
            "base": self.base_branch,
            "name": self.workflow_name,
            "created": f">={date_90_days_ago}",
            "sort": "updated",
            "direction": "desc",
            "per_page": 100,
        }
        headers = {"Authorization": f"token {self.github_token}"}

        # Pagination loop for PRs (GitHub API returns 100 max per page)
        while url and found_count < self.max_runs:
            print(url)
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            runs = response.json()
            if not runs:
                break
            viable_runs = list(
                filter(
                    lambda run: run["run_attempt"] > 1 or run["conclusion"] != "success",
                    runs["workflow_runs"],
                )
            )
            print(f"  {len(viable_runs)} viable runs")

            # for run in tqdm(viable_runs):
            for run in viable_runs:
                metadata = self.get_run_metadata(remote, run)
                if metadata is not None and metadata not in data:
                    data.append(metadata)
                    found_count += 1

            with open(output_file, "w") as f:
                json.dump(data, f, indent=2)
            if "next" in response.links and url:
                url = response.links["next"]["url"]
            else:
                break


def main():
    parser = argparse.ArgumentParser(
        prog="workflow_miner", description="Scrape GitHub CI actions in search of flaky tests."
    )

    parser.add_argument(
        "-t",
        "--github-token",
        help="GitHub token. If supplied, this value overrides the .env file.",
        default=os.getenv("GITHUB_TOKEN"),
    )
    parser.add_argument("-o", "--repo-owner", help="Github owner of the repo.", required=True)
    parser.add_argument("-n", "--repo-name", help="Name of the repo.", required=True)
    parser.add_argument(
        "-b",
        "--base-branch",
        help="Base branch to consider when looking at pull requests. Defaults to `main`.",
        default="main",
    )
    parser.add_argument("-w", "--workflow-name", help="Name of the workflow to consider, e.g. tests.yaml.")
    parser.add_argument(
        "-m",
        "--max-runs",
        help=(
            "Maximum number of runs to collect. "
            "Useful for larger repos to avoid hitting the rate limit. Defaults to 50."
        ),
        default=50,
        type=int,
    )
    parser.add_argument("-l", "--local-repo-path", help="Path to clone the remote repo.")
    args = parser.parse_args()
    if not args.github_token:
        raise ValueError("Please provide a GitHub authentication token either via the -t option of a .env file.")
    if not args.local_repo_path:
        args.local_repo_path = os.path.join("repos", args.repo_owner, args.repo_name)
    os.makedirs(args.local_repo_path, exist_ok=True)
    if not os.listdir(args.local_repo_path):
        git.Repo.clone_from(f"https://github.com/{args.repo_owner}/{args.repo_name}.git", args.local_repo_path)

    repo_miner = RepoMiner(
        github_token=args.github_token,
        repo_owner=args.repo_owner,
        repo_name=args.repo_name,
        local_repo_path=args.local_repo_path,
        base_branch=args.base_branch,
        workflow_name=args.workflow_name,
        max_runs=args.max_runs,
    )
    repo_miner.scrape_repo()


if __name__ == "__main__":
    main()
