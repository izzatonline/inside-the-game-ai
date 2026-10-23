#!/usr/bin/env bash
# Deploy Inside the Game to Azure Container Apps (keyless, scales to zero).
# Usage: infra/deploy.sh <resource-group> <foundry-ai-account-name> <model-deployment> [acr-name]
# Requires: az login, Docker. Run from the project root. Re-run to ship a new version.
set -euo pipefail
RG=$1; AI=$2; MODEL=$3; ACR=${4:-itgacr$(az group show -n "$RG" --query id -o tsv | shasum | cut -c1-8)}
az provider register -n Microsoft.App --wait
az provider register -n Microsoft.OperationalInsights --wait
az provider register -n Microsoft.ContainerRegistry --wait
az acr show -n "$ACR" -g "$RG" >/dev/null 2>&1 || az acr create -n "$ACR" -g "$RG" --sku Basic --admin-enabled false >/dev/null
TAG=$(date +%Y%m%d%H%M%S)
IMAGE="$ACR.azurecr.io/itg:$TAG"
az acr login -n "$ACR"
docker build --platform linux/amd64 -t "$IMAGE" .
docker push "$IMAGE"
az deployment group create -g "$RG" -f infra/main.bicep \
  -p image="$IMAGE" acrName="$ACR" aiAccountName="$AI" modelDeployment="$MODEL" \
  --query properties.outputs.url.value -o tsv
