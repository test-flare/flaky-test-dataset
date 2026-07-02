"""
This module contains unit tests for the workflow_miner module.
"""

from dotenv import load_dotenv
import os
from workflow_miner import parse_test_failures, WorkflowMiner

load_dotenv()


def test_parse_test_failures():
    """
    Test that we can identify failed tests from pytest logs.
    """
    log = """
    =========================== short test summary info ============================
    FAILED tests/components/device_tracker/test_entity.py::test_attr_location_name_deprecation_warning -
    AssertionError: assert 'is setting the deprecated _attr_location_name attribute' in ''
    where '' = <_pytest.logging.LogCaptureFixture object at 0x7fa9b99781a0>.text
"""
    assert parse_test_failures(log) == [
        "tests/components/device_tracker/test_entity.py::test_attr_location_name_deprecation_warning"
    ]
