#!/bin/bash
# Manual script to increase memory limits on running AMP deployment
# Use this AFTER deployment if you need to adjust limits without redeploying

# Get the deployment name (adjust namespace and deployment name as needed)
NAMESPACE="dp-default-default-default-ccb66d74"
DEPLOYMENT="financeinsightservice-default-9e218f68"

echo "Patching deployment $DEPLOYMENT in namespace $NAMESPACE..."
echo "Setting memory limits to 1Gi and requests to 768Mi"

docker exec k3d-amp-local-server-0 kubectl patch deployment -n "$NAMESPACE" "$DEPLOYMENT" \
  --type='json' \
  -p='[
    {
      "op": "replace",
      "path": "/spec/template/spec/containers/0/resources/limits/memory",
      "value": "1Gi"
    },
    {
      "op": "replace",
      "path": "/spec/template/spec/containers/0/resources/limits/cpu",
      "value": "1000m"
    },
    {
      "op": "replace",
      "path": "/spec/template/spec/containers/0/resources/requests/memory",
      "value": "768Mi"
    },
    {
      "op": "replace",
      "path": "/spec/template/spec/containers/0/resources/requests/cpu",
      "value": "500m"
    }
  ]'

echo ""
echo "Waiting for new pod to start..."
sleep 5

echo "Current pod status:"
docker exec k3d-amp-local-server-0 kubectl get pods -n "$NAMESPACE" | grep financeinsight

echo ""
echo "Verifying new resource limits:"
docker exec k3d-amp-local-server-0 kubectl get deployment -n "$NAMESPACE" "$DEPLOYMENT" \
  -o jsonpath='{.spec.template.spec.containers[0].resources}' | jq .

echo ""
echo "Done! Pod will restart with new memory limits."
