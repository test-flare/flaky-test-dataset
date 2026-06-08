#!/bin/bash
cd core
git reset --hard
git fetch origin $1
git checkout $1
./script/setup
