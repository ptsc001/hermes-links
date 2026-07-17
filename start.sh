#!/bin/bash
cd /data/hermes-links
set -a
source .env
set +a
exec python3 main.py
