# 🔑 Quick Reference: TrueCharts Cluster Commands

## 📦 Find Anything in Your Cluster

### List All Apps
```bash
# All pods across namespaces
kubectl get pods -A

# Media apps only (where jellyfin, immich are)
kubectl get pods -n media

# Filter by app name
kubectl get pods -n media -l app.kubernetes.io/name=jellyfin
```

### Check Status
```bash
# All services
kubectl get svc -A

# All ingresses (URLs)
kubectl get ingress -A

# PVCs and data locations
kubectl get pvc -A -o wide

# Helm releases
kubectl get helmrelease -A
```

### Check Events
```bash
# Recent events
kubectl get events -A --sort-by='.lastTimestamp'

# Events for specific namespace
kubectl get events -n media -A --sort-by='.lastTimestamp'
```

---

## 🎬 Common Tasks

### Jellyfin Operations
```bash
# Port-forward jellyfin (for API access)
kubectl port-forward -n media -p 8096 svc/jellyfin 5001:8096

# Wait for pod to be ready
kubectl rollout status deployment jellyfin-56b44757fc -n media

# Get recent logs
kubectl logs -n media jellyfin-56b44757fc-lx768 --tail=100
```

### Immich Operations
```bash
# Immich namespace
kubectl get pods -n immich

# Immich URL
kubectl get ingress -A | grep immich
```

### Dashboards
```bash
# Homepage dashboard
kubectl get deployment -A | grep homepage

# Kubernetes Dashboard
kubectl get deployment -n media kubernetes-dashboard
```

---

## 📊 Monitoring Commands

### Resource Usage
```bash
# CPU + Memory for all pods
kubectl top pods -A

# Memory only
kubectl get pods -A -o jsonpath='{range .items[*]}{"\n"}{"pod:  "}{.metadata.name}{": "}{.spec.containers[*].resources.requests.memory}{", "}{.spec.containers[*].resources.limits.memory}'
```

### Persistent Storage
```bash
# Storage usage
kubectl get pv -A -o jsonpath='{range .items[*]}{"\npv: "}{.metadata.name}{": "}{.spec.capacity.storage}{" "}{.metadata.ownerReferences[0].name}{"\n"}{end}'

# PVC usage
kubectl get pvc -A -o jsonpath='{range .items[*]}{"\npvc: "}{.metadata.name}{": "}{.status.capacity.storage}{" "}{.status.capacity.used}{" / "}{.status.capacity.storage}{"\n"}{end}'
```

---

## 🛠️ Debugging Patterns

### Pod Not Starting
```bash
# 1. Check pod status
kubectl get pods -n media

# 2. Describe for events
kubectl describe pod <pod-name> -n media

# 3. Check specific event
kubectl get events -n media --field-selector involvedObject.name=<pod-name>
```

### CrashLoop or Error
```bash
# Get full crash logs
kubectl logs -n media <pod-name> -c <container-name> --previous

# Check specific phase failure
kubectl describe pod <pod-name> -n media | grep -A 10 Error
```

### Database/Connection Issues
```bash
# Get service list
kubectl get svc -n media | grep database

# Test connectivity between pods
kubectl run debug --rm --restart=Never --image=bash:5.3 -- command -- \
    nslookup database-service.media.svc

# Check DNS resolution
kubectl exec -it debug -- nslookup <service-name>.<namespace>.svc.cluster.local
```

---

## 📦 GitOps Workflow

### After Making Config Changes
```bash
# 1. Wait for Git commit to propagate
# 2. Check if Flux has picked up
kubectl get helmrelease -n media <app-name>

# 3. Watch reconciliation
watch -n 5 'kubectl get helmrelease -n media <app-name>'

# 4. Verify pods are ready
kubectl get pods -n media | grep <app-name>
```

### Rolling Updates
```bash
# Check rollout status
kubectl rollout status deployment <deployment> -n media

# Scale if needed
kubectl scale deployment <deployment> --replicas=3 -n media

# Restart deployment (via repo update, not kubectl!)
# Edit config, commit, push!
```

---

## 🔑 Useful Environment Variables

### Cluster Access
```bash
# Kubernetes cluster URL
KUBERNETES_API=https://192.168.30.51:6443

# Current context
KUBECONFIG=~/.kube/config

# Git repo
K8S_REPO=/home/itzteajay/Projects/truecharts

# Cluster name
K8S_CLUSTER=main
```

---

## 🎯 One-Liners

### List All Running Apps
```bash
kubectl get pods -n media --no-headers | awk '{print $1, $2, $1}'
```

### Find Most Resource-Heavy Apps
```bash
kubectl top pods -n media --sort-by=cpu | head -10
```

### Check If Flux is Healthy
```bash
flux --kube-path ~/.kube/config get helmrelease -A | grep -i error
```

### Get Jellyfin URL
```bash
kubectl get ingress -A | grep jellyfin | awk '{
    for(i=1;i<=NF;i++) if($i ~ /jellyfin/) print $i
}'
```

---

## 📖 Glossary

| Term | Meaning |
|------|---|
| **HelmRelease** | Flux-managed Helm chart deployment |
| **GitRepo** | Flux repository object (not Kubernetes repo) |
| **Kustomization** | kustomize config for HelmRelease |
| **Flux CD** | Continuous Delivery tool using GitOps |
| **PVC** | PersistentVolumeClaim (your app's data) |
| **PV** | PersistentVolume (cluster storage) |
| **Talos** | Container native linux OS |

---

## ⚠️ Important Reminders

1. **Never use kubectl apply** – All changes via Git
2. **Commit descriptive messages** – Explain WHAT and WHY
3. **Check events** – They tell the story of what happened
4. **Watch, don't guess** – Use `watch` to monitor reconciliations
5. **Backup age.agekey** – Essential for decryption

---

**Keep this handy** for quick cluster management! 🚀
