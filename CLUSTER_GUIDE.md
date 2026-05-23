# 🏠 TrueCharts Cluster Navigation Guide
## itzteajay's Homelab Infrastructure

This document provides a comprehensive guide to navigating your TrueCharts Kubernetes cluster infrastructure.

---

## 📐 Cluster Architecture

### Cluster Details
- **Cluster Name:** `main`
- **Kubernetes Version:** 1.35+ (Talos v1.11.2)
- **GitOps Tool:** Flux v2.7.2
- **Cluster Management:** TrueCharts ClusterTool

### Repository Structure
```
~/Projects/truecharts/
├── clusters/
│   └── main/
│       ├── kubernetes/          # Kubernetes manifests
│       │   ├── apps/            # Application releases
│       │   ├── core/            # Core infrastructure
│       │   ├── flux-system/     # Flux CD configuration
│       │   ├── kube-system/     # System pods/configs
│       │   ├── my-apps/         # Application groups (jellyfin, immich, etc.)
│       │   ├── networking/      # Networking (ingresses, CNI)
│       │   ├── system/          # System services
│       │   └── flux-entry.yaml  # Flux reconciliation entry
│       ├── talos/               # Talos Linux configuration
│       ├── repositories/        # Helm repository configs
│       └── custom_images/       # Custom Docker images
├── .git/                        # Git repository
├── .sops.yaml                   # SOPS encryption config
└── age.agekey                   # SOPS encryption keys
```

---

## 🗂️ Namespace Organization

Your cluster uses multiple Kubernetes namespaces organized by application category:

| Namespace | Purpose | Example Apps |
|-----------|---------|--------------|
| `my-apps/media/` | Home/media servers | Jellyfin, Immich, OwnCast, Lidarr, Sonarr, Radarr |
| `_my-apps/downloaders/` | Downloaders & queue apps | Jellyseerr, Lidarr, Sonarr |
| `_my-apps/dashboards/` | Monitoring & dashboards | K8s Dashboard |
| `kube-system/` | Kubernetes system | CoreDNS, metrics-server |
| `flux-system/` | Flux CD components | Flux controllers, GitRepo |

---

## 🚀 Quick App Discovery

### 1. **Find Jellyfin & Media Apps**
```bash
# List all media apps
kubectl get pods -n media

# Get all services in media namespace
kubectl get all -n media

# Get services only (easiest view)
kubectl get svc -n media
```

### 2. **Find Downloader Apps**
```bash
kubectl get pods -n media -l app.kubernetes.io/name | grep -E "lidarr|radarr|sonarr|prowlarr|jellyseerr"
```

### 3. **Check PVCs/Data**
```bash
# List all PVCs in cluster
kubectl get pvc -A -o wide | grep -E "jellyfin|immich|media"

# Get PVC details
kubectl get pvc -n media <pvc-name> -o yaml
```

### 4. **View Secrets**
```bash
# Check secrets in media namespace
kubectl get secret -n media -o wide

# View specific secret
kubectl get secret <secret-name> -n media -o yaml
```

---

## 🔍 Finding Watch History & Playback Data

### For Jellyfin Apps:

#### Method 1: Jellyfin Web UI (Recommended)
```bash
# Your Jellyfin URL
https://jellyfin.hoth.systems

# Login with your credentials and check:
# - History tab
# - Recently Played
# - Play State & Progress
```

#### Method 2: Jellyfin HTTP API
```bash
# Port-forward the jellyfin service
kubectl port-forward -n media -p 8096 svc/jellyfin 5001:8096

# Access from: http://localhost:5001/

# Or use the external URL if configured
# https://jellyfin.hoth.systems
```

#### Method 3: Execute into Pod
```bash
# Get the specific pod name
kubectl get pods -n media -l app.kubernetes.io/name=jellyfin

# Execute into pod
kubectl exec -n media <pod-name> -- bash

# Inside the container:
# List files
ls -la /config/data/
# Check media library files
ls -la /config/data/data/playstate.dat 2>/dev/null || echo "Playstate may be in database"
```

#### Method 4: Database Queries
```bash
# Access SQLite database if exists
sqlite3 /config/data/data/jellyfin.db "SELECT * FROM PlaybackProgress ORDER BY PlayProgress DESC LIMIT 10;"
```

---

## 🔬 Deep Dive Commands

### Check Flux Status
```bash
# View all Helm releases
kubectl get helmrelease -A

# Watch reconciliation
watch -n 10 'kubectl get helmrelease -n media'
```

### Resource Monitoring
```bash
# Get CPU/Memory usage
kubectl top pods -n media

# Get memory usage
kubectl get pods --all-namespaces -o jsonpath='{range .items[*]}{"\npod: "}{.metadata.name}{": "}{.spec.containers[*].resources.requests.memory}{", "}{.spec.containers[*].resources.limits.memory}'
```

### Pod Health Check
```bash
# Check pod events
kubectl describe pod <pod-name> -n media

# Check events
kubectl get events -A --sort-by='.lastTimestamp'
```

---

## 🛠️ Essential kubectl Patterns

### Daily Operations
```bash
# 1. Check pod status
kubectl get pods -n media

# 2. Describe specific pod
kubectl describe pod <pod-name> -n media

# 3. Get recent logs
kubectl logs -n media <pod-name> --tail=100

# 4. Exec into pod (for debugging)
kubectl exec -n media <pod-name> -- bash

# 5. Get services
kubectl get svc -n media

# 6. Get ingress routes
kubectl get ingress -A

# 7. Monitor events
kubectl get events -A --sort-by='.lastTimestamp'
```

### GitOps-Compliant Operations
```bash
# ✅ CORRECT: Check current state
kubectl get helmrelease <app-name> -n <namespace>

# ✅ CORRECT: Check events
kubectl describe helmrelease <app-name> -n <namespace>

# ❌ NEVER: Direct kubectl apply
# kubectl apply -f <file>

# ❌ NEVER: Direct pod manipulation
# kubectl replace pod/...
```

---

## 📊 Custom Images Setup

Your cluster supports custom Docker images:

```bash
# Image location
ghcr.io/nerddotdad/<image-name>

# To add a custom app:
# 1. Create directory in custom_images/
mkdir -p custom_images/<app-name>

# 2. Create Dockerfile
# 3. Add app files
# 4. Commit and push
# Automatic build via GitHub Actions!
```

---

## 🔐 Secrets Management

### Using SOPS for Encryption
```bash
# Encrypt a config file
sops -e config.yaml > config.encrypted.yaml

# Decrypt
sops config.encrypted.yaml
```

### Accessing Secrets (When Needed)
```bash
# View secret in plain text (use cautiously)
kubectl get secret <secret-name> -n <namespace> -o yaml

# Better: Create new secret via GitOps
# Edit repository, commit, push
```

---

## 🎯 Troubleshooting Guide

### App Not Starting?
```bash
# 1. Check pod status
kubectl get pods -n media

# 2. Describe pod for events
kubectl describe pod <pod-name> -n media

# 3. Get recent logs
kubectl logs -n media <pod-name> --tail=500

# 4. Check PVC status
kubectl get pvc -n media

# 5. Check events
kubectl get events -n media --sort-by='.lastTimestamp'
```

### Database Connection Issues?
```bash
# Check database pod/container
kubectl exec -n media <pod-name> -- ps aux | grep database

# Test database connectivity
kubectl exec -n media <pod-name> -- ping database-service

# Check database logs
kubectl exec -n media <pod-name> -- tail -f /var/log/database.log
```

---

## 📱 Useful Tools

### Installed Utilities
```bash
flux --version        # Flux CD status
talosctl version      # Talos management
kubectl version       # Kubernetes CLI
clustertool help      # TrueCharts wrapper
```

---

## ✅ Checklist

Before deploying new apps:
- [ ] Flux is reconciling normally
- [ ] All PVCs are bound
- [ ] Secrets exist for dependencies
- [ ] Custom images are tested locally
- [ ] Config changes verified in Git

---

## 🔗 Documentation Links

- [TrueCharts Docs](https://truecharts.org)
- [Official Jellyfin Docs](https://jellyfin.org/docs)
- [Talos Linux](https://talos.dev)
- [Flux CD Docs](https://fluxcd.io)
- [SOPS](https://github.com/mozilla/sops)

---

**Maintained by:** itzteajay  
**GitOps Repository:** ~/Projects/truecharts  
**Last Synced:** $(date +%Y-%m-%d)
