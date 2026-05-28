## Diagnose (Flux HelmRelease)

```bash
# Replace NAME and NAMESPACE from the alert
export NAME=helmrelease-name
export NAMESPACE=target-namespace

flux get helmrelease "$NAME" -n "$NAMESPACE"
kubectl describe helmrelease "$NAME" -n "$NAMESPACE"
kubectl get helmrelease "$NAME" -n "$NAMESPACE" -o yaml | less

# Helm install job / chart fetch errors
kubectl get pods -n "$NAMESPACE" -l app.kubernetes.io/instance="$NAME"
kubectl logs -n flux-system deploy/helm-controller --tail=80
```

**Common causes**

| Symptom | Likely cause |
|---------|----------------|
| Chart not found | Wrong chart name/version or HelmRepository not ready |
| Install timeout | PVC pending, image pull, or resource limits |
| Upgrade failed | Values breaking upgrade; check `helm release` history |
| Stuck progressing | Stuck Helm hook or pre-upgrade job |
