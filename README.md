# Flaky Test Dataset
This dataset contains a collection of real flaky tests collected by mining GitHub CI actions for actions which initially failed and then subsequently passed.

# Directory and Data Structure
The flaky test data is in `./data`, which has the subdirectory structure `{repo_owner}/{repo_name}/{branch_name}.json`.
For example, data on failing tests from the `dev` branch of the `home-assistant/core` repository is in `data/home-assistant/core/dev.json`

Each JSON file contains a list of objects, each of which represents a workflow run with at least one failing test.
Each object has the following structure:
```
{
  "run_id": int,
  "run_attempt": int > 0,
  "created_at": "yyyy-mm-ddThh:mm:ss+hh:mm",
  "failed_tests": [
    {
      "test_id": "path/to/test_file.py::test_method",
      "introduced_in": commit_sha,
      "introduction_date": "yyyy-mm-ddThh:mm:ss+hh:mm"
    }
    ...
  ],
  "pull_request": {
    "number": int,
    "title": str,
    "created_at": "2026-05-26T10:23:23+00:00",
    "merge_sha": "yyyy-mm-ddThh:mm:ss+hh:mm",
    "source_sha": commit_sha,
    "target_sha": commit_sha
  }
}
```

# Collecting Additional Data
To update a repo or collect data from a new repo, you can run `src/workflow-miner.py` with the following arguments.
```
  -h, --help            show this help message and exit
  -t GITHUB_TOKEN, --github-token GITHUB_TOKEN
                        GitHub token. If supplied, this value overrides the .env file.
  -o REPO_OWNER, --repo-owner REPO_OWNER
                        Github owner of the repo.
  -n REPO_NAME, --repo-name REPO_NAME
                        Name of the repo.
  -b BASE_BRANCH, --base-branch BASE_BRANCH
                        Base branch to consider when looking at pull requests. Defaults to `main`.
  -w WORKFLOW_NAME, --workflow-name WORKFLOW_NAME
                        Name of the workflow to consider, e.g. tests.yaml.
  -m MAX_RUNS, --max-runs MAX_RUNS
                        Maximum number of failed runs to collect.
                        Useful for larger repos to avoid hitting the rate limit.
                        Defaults to 50.
  -l LOCAL_REPO_PATH, --local-repo-path LOCAL_REPO_PATH
                        Path to clone the remote repo.
```

For example, to collect the data for the `home-assistant/core` repository, we ran the following command to collect data
from the `dev` branch (the default branch of the repo) using the `ci.yaml` workflow (the CI test workflow).
```
python src/workflow_miner.py --repo-owner home-assistant --repo-name core --base-branch dev --workflow-name ci.yaml

```
This will create (or update) the JSON file that corresponds to the repo branch.
