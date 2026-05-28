# Contributing

## Questions
Please ask any questions about the Causal Testing Framework or surrounding concepts on the
[discussions board](https://github.com/test-flare/flaky-test-dataset/discussions). Before opening a new
discussion, please see whether a relevant one already exists - someone may have answered your question already.

## Reporting Bugs and Making Suggestions
Upon identifying any bugs or features that could be improved, please open an
[issue](https://github.com/test-flare/flaky-test-dataset/issues) and label with bug or feature suggestion. Every issue
should clearly explain the bug or feature to be improved and, where necessary, instructions to replicate. We also
provide templates for common scenarios when creating an issue.

## Contributing Additional Material
To contribute to our work, please ensure the following:

1. [Fork the repository](https://help.github.com/articles/fork-a-repo/) into your own GitHub account, and [clone](https://docs.github.com/en/repositories/creating-and-managing-repositories/cloning-a-repository) it to your local machine.
2. To contribute new data, follow the instructions in the [README](README.md#Collecting_Additional_Data) to collect data for your repo of choice.
3. Commit and [push your changes](https://docs.github.com/en/get-started/using-git/pushing-commits-to-a-remote-repository) to your remote fork, compare with `flaky-test-dataset/main`, and ensure any conflicts are resolved.
4. Create a draft [pull request](https://docs.github.com/en/get-started/quickstart/hello-world#opening-a-pull-request) (PR) from your branch, and ensure you have [linked](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls) it to any relevant issues in your description.
5. When all Continuous Integration (CI) actions pass, mark your PR as ready for review.

## Continuous Integration (CI) and Code Quality
Our CI tests include:
    - Build: Install the necessary Python and runtime dependencies.
    - Linting: [pylint](https://pypi.org/project/pylint/) is employed for our code linter and analyser.
    - Testing: We use [pytest](https://pytest.org/en/latest/) to develop and run tests.
    - Formatting: We use [black](https://pypi.org/project/black/) for our code formatting.

To find the other (optional) developer dependencies, please check `pyproject.toml`.

## Pre-commit Hooks
We use [pre-commit](https://pre-commit.com/) to automatically run code quality checks before each commit. This ensures consistent code style and catches issues early.

Automated checks include:

- Trailing whitespace removal
- End-of-file fixing
- Black formatting
- JSON validation
- isort import sorting
- Pylint code analysis

To use pre-commit:
```bash
# Install pre-commit hooks (one-time setup of .pre-commit-config.yaml)
pre-commit install

# Manually run hooks on all files (optional)
pre-commit run --all-files
```
