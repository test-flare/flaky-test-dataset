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
  "run_attempt": int,
  "created_at": "yyyy-mm-ddThh:mm:ssZ",
  "failed_tests": {
    "path/to/test_file.py::test_id": {
      "introduced_in": "commit_sha",
      "introduction_date": "yyyy-mm-ddThh:mm:ssZ",
      "passes": int, # Number of times the test passed when attempting to reproduce flaky behaviour
      "failures": int # Number of times the test failed when attempting to reproduce flaky behaviour
    },
    ...
  },
  "pull_request": {
    "number": int,
    "title": "PR message",
    "created_at": "yyyy-mm-ddThh:mm:ssZ",
    "merge_sha": "commit_sha",
    "source_sha": "commit_sha",
    "target_sha": "commit_sha"
  }
},
```

# Collecting Additional Data

## Setup

1. Create a new python virtual environment
```
virtualenv venv
```
2. Activate the virtual environment
```
source venv/bin/activate
```
3. Install the package
```
pip install .
```

### Collecting Data

To update a repo or collect data from a new repo, you can run `python src/workflow-miner.py` with the following arguments.
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

### Replicating Flaky Behaviour
Replicating flaky behaviour is slightly more involved than repository mining, but is still fairly straightforward.
To maximise reproducability, we use [Docker](https://docs.docker.com/) containers to execute the flaky test candidates.
Each repo therefore needs a Dockerfile, as well as scripts to set up the repo and run the tests.
These are mostly boilerplate, and we have included a script to generate these for you.
To do this, you can call
```
python src/replicate_flakiness.py --repo-owner $REPO_OWNER --repo-name $REPO_NAME --generate-template-scripts
```
This will generate three files in `data/$REPO_OWNER/$REPO_NAME`:
- `Dockerfile` contains instructions for Docker on how to set up the container up to and including cloning the
repository into the container.
This should be sufficient for most needs, but you may need to add extra system dependencies to the install command.
- `setup.sh` is a script to checkout the relevant commit and setup the repo by installing the necessary dependencies.
It contains all of the setup that could possibly vary between commits.
By default, this just calls `python -m uv sync --group dev` to set up a virtual environment and install the dependencies
using `uv`.
> [!NOTE]
> More complex repositories such as `home-assistant/core` tend to provide their own setup scripts.
> You should consult the README of the repo for more details.
- `test.sh` is a script to run the flaky test cases. By default, it just uses `uv` to run `pytest` from the virtual environment.

Once you have done this, you can then attempt to replicate the flaky behaviour by calling
```
python src/replicate_flakiness.py --repo-owner $REPO_OWNER --repo-name $REPO_NAME --branch-name $BRANCH_NAME --max-repeats 100
```
This will attempt to run each flaky test candidate 100 times.
The results will overwrite the `passes` and `failures` keys for each test in `data/$REPO_OWNER/$REPO_NAME/$BRANCH_NAME.json`.
