#!/usr/bin/env bash

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
ENDPOINT_NAME="${ENDPOINT_NAME:-audio-diarization-demo}"

aws sagemaker describe-endpoint \
  --region "$AWS_REGION" \
  --endpoint-name "$ENDPOINT_NAME" \
  --query '{
    Status:EndpointStatus,
    CurrentInstances:ProductionVariants[0].CurrentInstanceCount,
    DesiredInstances:ProductionVariants[0].DesiredInstanceCount,
    InstanceType:ProductionVariants[0].InstanceType
  }'
