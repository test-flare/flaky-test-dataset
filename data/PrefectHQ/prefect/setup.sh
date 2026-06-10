#!/bin/bash
cd prefect
git reset --hard
git fetch origin $1
git checkout $1

# Commands to set up and install the repo
python -m uv sync --group dev
        