#!/bin/bash
cd core
git reset --hard
git fetch origin $1
git checkout $1

cd ..
python fix_dependencies.py

cd core
./script/setup
