#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(
  cd "$(dirname "${BASH_SOURCE[0]}")" &&
  pwd
)"

source "${SCRIPT_DIR}/env.sh"

RESOURCE_ID="endpoint/${ENDPOINT_NAME}/variant/${VARIANT_NAME}"

get_status() {
  aws sagemaker describe-endpoint \
    --region "$AWS_REGION" \
    --endpoint-name "$ENDPOINT_NAME" \
    --query 'EndpointStatus' \
    --output text
}

get_current() {
  aws sagemaker describe-endpoint \
    --region "$AWS_REGION" \
    --endpoint-name "$ENDPOINT_NAME" \
    --query 'ProductionVariants[0].CurrentInstanceCount' \
    --output text
}

get_desired() {
  aws sagemaker describe-endpoint \
    --region "$AWS_REGION" \
    --endpoint-name "$ENDPOINT_NAME" \
    --query 'ProductionVariants[0].DesiredInstanceCount' \
    --output text
}

echo "=== Audio Diarization Demo: ON ==="

echo
echo "1. Keeping public broker disabled during startup..."

aws lambda put-function-concurrency \
  --region "$AWS_REGION" \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --reserved-concurrent-executions 0 \
  >/dev/null

echo "Broker disabled."

echo
echo "2. Waiting for any existing SageMaker update to finish..."

while true; do
  STATUS="$(get_status)"
  CURRENT="$(get_current)"
  DESIRED="$(get_desired)"

  echo \
    "Status=${STATUS} CurrentInstances=${CURRENT} DesiredInstances=${DESIRED}"

  if [ "$STATUS" = "InService" ]; then
    break
  fi

  if [ "$STATUS" = "Failed" ] || \
     [ "$STATUS" = "OutOfService" ]; then
    echo "ERROR: SageMaker endpoint is in state: ${STATUS}"
    exit 1
  fi

  sleep 10
done

echo
echo "3. Setting SageMaker capacity to one GPU..."

aws application-autoscaling register-scalable-target \
  --region "$AWS_REGION" \
  --service-namespace sagemaker \
  --resource-id "$RESOURCE_ID" \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 1 \
  --max-capacity 1 \
  >/dev/null

echo "Scaling target configured."

echo
echo "4. Waiting for GPU instance..."

while true; do
  STATUS="$(get_status)"
  CURRENT="$(get_current)"
  DESIRED="$(get_desired)"

  echo \
    "Status=${STATUS} CurrentInstances=${CURRENT} DesiredInstances=${DESIRED}"

  if [ "$STATUS" = "Failed" ] || \
     [ "$STATUS" = "OutOfService" ]; then
    echo "ERROR: SageMaker endpoint is in state: ${STATUS}"
    exit 1
  fi

  if [ "$STATUS" = "InService" ] && \
     [ "$CURRENT" = "1" ] && \
     [ "$DESIRED" = "1" ]; then
    break
  fi

  sleep 10
done

echo
echo "5. Enabling public broker..."

aws lambda put-function-concurrency \
  --region "$AWS_REGION" \
  --function-name "$LAMBDA_FUNCTION_NAME" \
  --reserved-concurrent-executions 2 \
  >/dev/null

echo
echo "=== Demo is ON ==="
echo "Lambda broker: enabled"
echo "SageMaker GPUs: 1"
