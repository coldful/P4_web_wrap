#!/usr/bin/env bash
set -euo pipefail

uvicorn p4_web.main:app --reload

