# 🗺️ Cluster Navigation Map

```
┌─────────────────────────────────────────────────────────────────┐
│                         KUBERNETES CLUSTER                       │
│                        (192.168.30.51:6443)                     │
└─────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌─────────────────┐         ┌────────────────┐
│   my-apps/    │         │  kube-system/   │         │  flux-system/  │
│ └─────────────┘         │ └───────────────┘         │ └──────────────┘ │
│                   │     │                   │         │                │
│  ┌───────────────┴──┐  │    ┌─────────────┴┐      │    ┌──────────┐  │
│  │   media/         │  │    │   core/      │      │    │   ...    │  │
│  │  ┌────────────┐  │  │    │ └────────────┴┘      │    │          │  │
│  │  │ jellyfin/  │  │  │    │                   │      │            │  │
│  │  │ immich/    │  │  │    │   networking/     │      │            │  │
│  │  │ owncast/   │  │  │    │  └────────────────┼─┐  │    ┌────────┐ │  │
│  │  │ lidarr/    │  │  │    │  │                   │    │    │       │ │  │
│  │  │ radarr/    │  │  │    │  │     system/      │    │    │       │ │  │
│  │  │ ...        │  │  │    │  │ └────────────────┼─┘    │    │       │ │  │
│  │  └────────────┘  │  │    │  └─────────────────┐ │      │    │       │ │  │
│  └──────────────────┴──┘    │                     │   │      │    │       │ │  │
│                              │       system pods    │   │       │    │       │ │  │
└─────────────────────────────┴───────────────────────┴─────────────────┴────┘
                                    │
                                    ▼
                    ┌──────────────────────────┐
                    │  Apps are deployed via   │
                    │  Flux (GitOps)           │
                    │                          │
                    │  Source:                 │
                    │  ~/Projects/truecharts/  │
                    │                          │
                    │  Edit config → Commit →  │
                    │  Push → Flux auto-applies│
                    └──────────────────────────┘
```

---

## 📂 Directory Tree

```
~/Projects/truecharts/
├── .cursorrules           # Rules for AI assistants (this is me!)
├── README.md              # Basic info
├── clusters/
├── custom_images/         # Custom Docker images
└── kubernetes/
    ├── apps/              # Application definitions
    ├── core/              # Core infrastructure
    ├── flux-system/       # Flux configuration
    ├── kube-system/       # K8s system components
    ├── networking/        # Ingress, CNI, etc.
    ├── my-apps/           # My applications
    │   ├── dashboards/    # Monitoring UI
    │   ├── downloaders/   # Downloaders
    │   ├── immich/       # Immich instance
    │   ├── media/        # Jellyfin, etc.
    │   ├── ...
    ├── system/            # System services
    └── talos/             # Talos config
```

---

## 🎯 Quick Find: Commands by Goal

### Goal: Find Jellyfin Data
```bash
# 1. Check what's running
kubectl get pods -n media

# 2. Find the data volume
kubectl get pvc -n media | grep jellyfin

# 3. Access files
kubectl exec -n media jellyfin-<pod> -- ls /config/

# 4. Check pod logs
kubectl logs -n media jellyfin-<pod>
```

### Goal: Find Immich Data
```bash
kubectl get pods -n immich
kubectl get svc -n immich
```

### Goal: Access Downloader Apps
```bash
kubectl get pods -n downloaders
```

### Goal: View Dashboards
```bash
kubectl get deployment -n my-apps dashboards
```

---

## 🔗 External URLs

Your cluster exposes these services externally:

| Service | URL/Port | Namespace | Purpose |
|---------|----------|-----------|---------|
| Jellyfin | jellyfin.hoth.systems | media | Media server |
| Immich | (configured via ingress) | immich | Photo library |
| OwnCast | (configured via ingress) | owncast | Radio host |
| Dashboards | (configured via ingress) | my-apps | Monitoring |

To find ingress URLs:
```bash
kubectl get ingress -A
```

---

## 🛠️ Workflow Examples

### Deploying a New App
```bash
# 1. Go to my-apps/<app-name>/
cd ~/Projects/truecharts/clusters/main/kubernetes/my-apps/

# 2. Create app directory
mkdir <app-name>

# 3. Create ks.yaml with app definition
# 4. Create app/kustomization.yaml
# 5. Create app/helm-release.yaml

# 6. Commit and push
git add my-apps/<app-name>/
git commit -m "Add <app-name> app"
git push

# 7. Flux will automatically deploy!
# 8. Monitor with:
kubectl get pods -n <namespace>
```

### Finding Secrets
```bash
# List all secrets
kubectl get secrets -A

# Find secret for specific app
kubectl get secrets -n media | grep -i jellyfin

# View secret contents
kubectl get secret <secret-name> -n namespace -o yaml
```

---

## 📊 Architecture Overview

### Components
- **Talos 1.11.2** - Container-native Linux OS
- **Kubernetes 1.35+** - Container orchestration
- **Flux v2.7.2** - GitOps controller
- **Helm** - Chart/package manager
- **TrueCharts** - Helm charts library
- **Longhorn** - Distributed storage (for PVCs)

### Storage
- **PVCs** claim from storage class
- **Longhorn** provides RWO/RWX storage
- **100Gi** PVCs common for media

---

## 🎨 Visual Structure

```
┌────────────────────────────────────────────────────┐
│                 FLUX GITOPS SYSTEM                 │
├────────────────────────────────────────────────────┤
│                                                     │
│  [Git Repo] ──► [Flux Controller] ──► [K8s API]  │
│       │              │                     │       │
│       ▼              ▼                     ▼       │
│  [Config Files]  [Reconciliation]    [Running Pods│
│                                                     │
│  Edit config → Commit → Push → Flux applies        │
└────────────────────────────────────────────────────┘
```

---

## 🔐 Security Notes

### Secrets Access
- Never commit plain-text secrets
- Use SOPS for encryption
- age.agekey for decryption
- .sops.yaml for SOPS configuration

### Never Do
- `kubectl apply` directly (breaks GitOps)
- Manually edit cluster resources
- Commit secrets to repo

---

## 📚 File Formats

### Kustomization (kustomization.yaml)
```yaml
resources:
  - app/helm-release.yaml
  - app/kustomization.yaml
  
images:
  - name: jellyfin
    newName: ghcr.io/your-registry/jellyfin
    newTag: latest
```

### Helm Release (helm-release.yaml)
```yaml
apiVersion: helm.fluxcd.io/v2beta1
kind: HelmRelease
metadata:
  name: jellyfin
  namespace: media
spec:
  values: {...}
  helmParams:
    createCRDs: false
```

---

## 🚀 Flux Commands

```bash
# Check all releases
flux get helmrelease -A

# Watch reconciliation
flux watch helmrelease <name> -n <ns>

# Get events
kubectl get events -n flux-system
```

---

**Last Updated:** 2026-05-22  
**Maintained by:** itzteajay  
**GitOps Workflow:** Always edit repo → commit → push
