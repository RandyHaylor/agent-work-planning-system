#!/usr/bin/env bash
cd "$(dirname "$0")"
python3 -m unittest -v 2>&1
