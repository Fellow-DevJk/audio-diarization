#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

RESOURCE_ID="endpoint/${ENDPOINT_NAME}/variant/${VARIANT_NAME}"

echo "=== Audio Diarization Demo: ON ==="

echo
echo "1. Starting SageMaker GPU..."

aws application-autoscaling register-scalable-target \
  --region "$AWS_REGION" \
  --service-namespace sagemaker \
  --resource-id "$RESOURCE_ID" \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 1 \
  --max-capacity 1

aws sagemaker update-endpoint-weights-and-capacities \
  --region "$AWS_REGION" \
  --endpoint-name "$ENDPOINT_NAME" \
  --desired-weights-and-capacities \
    VariantName="$VARIANT_NAME",DesiredInstanceCount=1

echo
echo "Waiting for GPU instance..."

while true; do
    CURRENT=$(
        aws sagemaker describe-endpoint \
          --region "$AWS_REGION" \
          --endpoint-name "$ENDPOINT_NAME" \
          --query 'ProductionVariants[0].CurrentInstanceCount' \
          --output text
    )

    STATUS=$(
        aws sagemaker describe-endpoint \
          --region "$AWS_REGION" \
          --endpoint-name "$ENDPOINT_NAME" \
          --query 'EndpointStatus' \
          --output text
    )

    echo "Status=${STATUS} CurrentInstances=${CURRENT}"

    if [ "$STATUS" = "InService" ] && [ "$CURRENT" = "1" ]; then
        break
    fi

    sleep 10
done

echo
echo "2. Enabling public broker..."

aws lambda put-function-concurrency \
  --region "$AWS_REGION" \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --reserved-concurrent-executions 2

echo
echo "Demo is ON."
echo "Lambda broker: enabled"
echo "SageMaker GPUs: 1"
