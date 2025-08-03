#!/bin/bash

dir="$(cd -P -- "$(dirname -- "$0")" && pwd -P)"
cd "$dir"

clear && python3 mdweb.py