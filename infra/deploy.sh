#!/usr/bin/env bash
# Usage: infra/deploy.sh <resource-group> <acr-name> [foundry-endpoint] [foundry-model]
# Requires: az login. Creates nothing until you run it; review infra/main.bicep first.
set -euo pipefail
RG=$1; ACR=$2; FEP=${3:-}; FM=${4:-}
az acr build -r "$ACR" -t itg:latest .
az deployment group create -g "$RG" -f infra/main.bicep \
  -p image="$ACR.azurecr.io/itg:latest" acrName="$ACR" foundryProjectEndpoint="$FEP" foundryModel="$FM" \
  --query properties.outputs
