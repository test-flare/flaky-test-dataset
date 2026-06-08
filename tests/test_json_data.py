"""
Test that the data follows the predefined schema.
"""

import json
from glob import glob
import pytest
import jsonschema


@pytest.mark.parametrize(
    "repo",
    [pytest.param(repo, id=repo) for repo in glob("data/*/*", recursive=True)],
)
def test_json_data_present(repo):
    data_files = glob(f"{repo}/*.json")
    assert data_files, f"No JSON file found for repo {repo}."
    with open("schemas/actions.schema.json") as f:
        schema = json.load(f)
    for data_file in data_files:
        with open(data_file) as f:
            runs = json.load(f)
        assert runs, f"Data for {data_file} is empty"
        jsonschema.protocols.Validator.validate(runs, schema)
