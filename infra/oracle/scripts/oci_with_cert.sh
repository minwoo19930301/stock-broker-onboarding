#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
OCI_BIN="${PROJECT_ROOT}/.tools/oci-cli/bin/oci"
CERT_BUNDLE="${OCI_CERT_BUNDLE:-/tmp/macos-all-certs.pem}"

exec "${OCI_BIN}" --cert-bundle "${CERT_BUNDLE}" "$@"
