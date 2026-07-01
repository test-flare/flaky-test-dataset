#!/bin/bash
cd core
git reset --hard
git fetch origin $1
git checkout $1

cd ..
python fix_dependencies.py

cd core
./script/setup

# TODO: Delete me once the outstanding PRs have been merged
.venv/bin/pip install pytest git+https://github.com/test-flare/pytest-flakefighters.git@5b5df80d4679f20fd563221553c0b827d6852027
