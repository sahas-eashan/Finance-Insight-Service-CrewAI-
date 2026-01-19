#!/bin/bash
# Keep the finance insight deployment patched with 8GB memory
# Run this in background: ./keep-memory-patched.sh &

NAMESPACE="dp-default-default-default-ccb66d74"
DEPLOYMENT="finance-insight-default-965f1bd1"

echo "Starting memory patch monitor for $DEPLOYMENT..."

while true; do
    # Check current memory limit
    CURRENT_MEMORY=$(sudo docker exec k3d-amp-local-server-0 kubectl get deployment -n $NAMESPACE $DEPLOYMENT -o jsonpath='{.spec.template.spec.containers[0].resources.limits.memory}' 2>/dev/null)
    
    if [ "$CURRENT_MEMORY" != "8Gi" ]; then
        echo "[$(date)] Memory is $CURRENT_MEMORY, patching to 8Gi..."
        sudo docker exec k3d-amp-local-server-0 kubectl patch deployment -n $NAMESPACE $DEPLOYMENT \
            --type='json' \
            -p='[{"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/memory", "value": "8Gi"}, 
                 {"op": "replace", "path": "/spec/template/spec/containers/0/resources/limits/cpu", "value": "4000m"}, 
                 {"op": "replace", "path": "/spec/template/spec/containers/0/resources/requests/memory", "value": "2Gi"}]' \
            2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo "[$(date)] Successfully patched to 8Gi"
        fi
    else
        echo "[$(date)] Memory is correct: $CURRENT_MEMORY"
    fi
    
    # Check every 30 seconds
    sleep 30
done
