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

echo "=== Audio Diarization Demo: OFF ==="

echo
echo "1. Disabling public broker..."

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
    echo
    echo "ERROR: SageMaker endpoint is in state: ${STATUS}"
    exit 1
  fi

  sleep 10
done

echo
echo "3. Allowing SageMaker Async Inference to scale to zero..."

aws application-autoscaling register-scalable-target \
  --region "$AWS_REGION" \
  --service-namespace sagemaker \
  --resource-id "$RESOURCE_ID" \
  --scalable-dimension sagemaker:variant:DesiredInstanceCount \
  --min-capacity 0 \
  --max-capacity 1 \
  >/dev/null

echo "Scaling target configured: min=0 max=1."

echo
echo "4. Checking current GPU capacity..."

STATUS="$(get_status)"
CURRENT="$(get_current)"
DESIRED="$(get_desired)"

echo \
  "Status=${STATUS} CurrentInstances=${CURRENT} DesiredInstances=${DESIRED}"

if [ "$CURRENT" = "0" ] && \
   [ "$DESIRED" = "0" ]; then

  echo "GPU capacity is already zero."

else
  echo
  echo "5. Requesting zero GPU instances..."

  aws sagemaker update-endpoint-weights-and-capacities \
    --region "$AWS_REGION" \
    --endpoint-name "$ENDPOINT_NAME" \
    --desired-weights-and-capacities \
      VariantName="$VARIANT_NAME",DesiredInstanceCount=0 \
    >/dev/null

  echo "Scale-down request submitted."
fi

echo
echo "6. Waiting for GPU instance count to reach zero..."

while true; do
  STATUS="$(get_status)"
  CURRENT="$(get_current)"
  DESIRED="$(get_desired)"

  echo \
    "Status=${STATUS} CurrentInstances=${CURRENT} DesiredInstances=${DESIRED}"

  if [ "$STATUS" = "Failed" ] || \
     [ "$STATUS" = "OutOfService" ]; then
    echo
    echo "ERROR: SageMaker endpoint is in state: ${STATUS}"
    exit 1
  fi

  if [ "$STATUS" = "InService" ] && \
     [ "$CURRENT" = "0" ] && \
     [ "$DESIRED" = "0" ]; then
    break
  fi

  sleep 10
done

echo
echo "=== Demo is OFF ==="
echo "Lambda broker: disabled"
echo "SageMaker GPUs: 0"
