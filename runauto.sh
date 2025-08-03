#!/bin/bash

dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"
cd "$dir"

find . -name '*.py' | entr -n -r bash -c 'clear; python3 mdweb.py'