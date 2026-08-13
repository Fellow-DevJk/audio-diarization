#!/usr/bin/env bash

set -euo pipefail

if [ "${1:-}" = "serve" ]; then
    shift

    echo "Starting SageMaker inference server..."

    exec /opt/nvidia/nvidia_entrypoint.sh \
        python3.10 -m uvicorn \
        backend.app.main:app \
        --host 0.0.0.0 \
        --port 8080
fi

exec /opt/nvidia/nvidia_entrypoint.sh "$@"
