#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/env.sh"

RESOURCE_ID="endpoint/${ENDPOINT_NAME}/variant/${VARIANT_NAME}"

echo "=== Audio Diarization Demo: OFF ==="
echo
echo "1. Disabling public broker..."

aws lambda put-function-concurrency \
  --region "$AWS_REGION" \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --reserved-concurrent-executions 0

echo "Broker disabled."

echo
echo "2. Allowing SageMaker to scale to zero..."

aws application-autoscaling register-scalable-target \
  --region "$AWS_REGION" \
  --service-namespace sagemaker \
  --resource-id "$RESOURCE_ID" \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 0 \
  --max-capacity 1

echo
echo "3. Requesting zero GPU instances..."

aws sagemaker update-endpoint-weights-and-capacities \
  --region "$AWS_REGION" \
  --endpoint-name "$ENDPOINT_NAME" \
  --desired-weights-and-capacities \
    VariantName="$VARIANT_NAME",DesiredInstanceCount=0

echo
echo "Waiting for GPU instance count to reach zero..."

while true; do
    CURRENT=$(
        aws sagemaker describe-endpoint \
          --region "$AWS_REGION" \
          --endpoint-name "$ENDPOINT_NAME" \
          --query 'ProductionVariants[0].CurrentInstanceCount' \
          --output text
    )

    echo "CurrentInstances=${CURRENT}"

    if [ "$CURRENT" = "0" ]; then
        break
    fi

    sleep 10
done

echo
echo "Demo is OFF."
echo "Lambda broker: disabled"
echo "SageMaker GPUs: 0"
