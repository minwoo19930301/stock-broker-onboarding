#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
BACKEND_ROOT="${PROJECT_ROOT}/backend"

cd "${BACKEND_ROOT}"
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart stock-broker-onboarding-api
sudo systemctl status stock-broker-onboarding-api --no-pager
