#!/usr/bin/env bash
cd "$(dirname "$0")"
TZ=Pacific/Auckland python3 -m unittest -v 2>&1
