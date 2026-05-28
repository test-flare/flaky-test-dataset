"""
Test that the data follows the predefined schema.
"""

import json
import os
from glob import glob
import pytest
import jsonschema


@pytest.mark.parametrize(
    "filename",
    [pytest.param(filename, id=filename) for filename in filter(os.path.isfile, glob("data/**/*", recursive=True))],
)
def test_json_syntax(filename):
    assert filename.endswith(".json"), f"{filename} not a json file."
    with open("schemas/actions.schema.json") as f:
        schema = json.load(f)
    with open(filename) as f:
        runs = json.load(f)
    jsonschema.protocols.Validator.validate(runs, schema)
