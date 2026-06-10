#!/bin/bash
cd prefect
.venv/bin/python -m uv run pytest $@

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
        