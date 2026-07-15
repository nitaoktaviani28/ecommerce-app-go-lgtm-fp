#!/bin/bash
# Deploy LGTM-FP Stack to AKS
# Run this from Azure Cloud Shell or local terminal with kubectl access

set -e

echo "=== Creating monitoring namespace ==="
kubectl create ns monitoring --dry-run=client -o yaml | kubectl apply -f -

echo ""
echo "=== Adding Grafana Helm repo ==="
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

echo ""
echo "=== Deploying Alloy ConfigMap ==="
kubectl apply -f lgmt-fp/deploy-aks/alloy-configmap.yaml

echo ""
echo "=== Deploying Loki ==="
helm upgrade --install loki grafana/loki \
  -n monitoring \
  -f lgmt-fp/deploy-aks/loki-values.yaml \
  --wait --timeout 5m

echo ""
echo "=== Deploying Mimir ==="
helm upgrade --install mimir grafana/mimir-distributed \
  -n monitoring \
  -f lgmt-fp/deploy-aks/mimir-values.yaml \
  --wait --timeout 5m

echo ""
echo "=== Deploying Tempo ==="
helm upgrade --install tempo grafana/tempo-distributed \
  -n monitoring \
  -f lgmt-fp/deploy-aks/tempo-values.yaml \
  --wait --timeout 5m

echo ""
echo "=== Deploying Pyroscope ==="
helm upgrade --install pyroscope grafana/pyroscope \
  -n monitoring \
  -f lgmt-fp/deploy-aks/pyroscope-values.yaml \
  --wait --timeout 5m

echo ""
echo "=== Deploying Alloy ==="
helm upgrade --install alloy grafana/alloy \
  -n monitoring \
  -f lgmt-fp/deploy-aks/alloy-values.yaml \
  --wait --timeout 5m

echo ""
echo "=== Deploying Grafana (latest with Drilldown) ==="
helm upgrade --install grafana grafana/grafana \
  -n monitoring \
  -f lgmt-fp/deploy-aks/grafana-values.yaml \
  --wait --timeout 5m

echo ""
echo "=== Deployment Complete ==="
echo ""
kubectl get pods -n monitoring
echo ""
kubectl get svc -n monitoring | grep -E "NAME|LoadBalancer"
