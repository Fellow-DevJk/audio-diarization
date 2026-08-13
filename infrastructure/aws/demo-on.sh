#!/usr/bin/env bash

set -euo pipefail

AWS_REGION="${AWS_REGION:-ap-south-1}"
ENDPOINT_NAME="${ENDPOINT_NAME:-audio-diarization-demo}"
VARIANT_NAME="${VARIANT_NAME:-AllTraffic}"

RESOURCE_ID="endpoint/${ENDPOINT_NAME}/variant/${VARIANT_NAME}"

echo "Enabling demo endpoint..."
echo "Region:   ${AWS_REGION}"
echo "Endpoint: ${ENDPOINT_NAME}"

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
echo "Waiting for one instance..."

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
echo "Demo endpoint is ON."
