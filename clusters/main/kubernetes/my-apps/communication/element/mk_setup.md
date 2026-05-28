---
title: Element setup & secrets
---

# Element Server Suite — setup notes

Supplemental guide for `element-server-suite` (manifest: `app/helm-release-ess.yaml`). Cluster secrets live in `clusters/main/clusterenv.yaml` (encrypt with `clustertool encrypt` before commit).

## URLs (from chart values)

| Service | Host |
|---------|------|
| Element Web | `https://element.${DOMAIN_0}` |
| Synapse | `https://matrix.${DOMAIN_0}` |
| Matrix Authentication Service | `https://mas.${DOMAIN_0}` |
| Element Admin | `https://admin.${DOMAIN_0}` |
| Matrix RTC | `https://mrtc.${DOMAIN_0}` |

Custom welcome page: `app/welcome.html` (mounted via chart).

## Clusterenv variables

| Variable | Purpose |
|----------|---------|
| `ELEMENT_DB_PASSWORD` | Synapse + MAS PostgreSQL user |
| `ELEMENT_DB_ROOT_PASSWORD` | CNPG cluster admin |
| `ELEMENT_REDIS_PASSWORD` | Redis (if enabled) |
| `ELEMENT_REGISTRATION_SECRET` | Registration / admin bootstrap |
| `ELEMENT_ADMIN_EMAIL` | Admin contact |
| `ELEMENT_JITSI_SECRET` | Jitsi (advanced / optional) |
| `ELEMENT_TURN_USERNAME` / `ELEMENT_TURN_PASSWORD` | TURN (optional) |
| `ELEMENT_EXTERNAL_IP` | External IP for TURN |
| `NFS_ELEMENT_MEDIA` | Optional NFS path for media |

Generate a registration secret:

```bash
openssl rand -hex 32
```

## Related manifests (same app folder)

| File | Role |
|------|------|
| `cnpg-postgresql.yaml` | CloudNative-PG cluster (Postgres for Synapse/MAS) |
| `cnpg-database-mas.yaml` | MAS database |
| `cnpg-*-credentials.yaml` | DB credentials |
| `cnpg-scheduled-backup.yaml` | Backups |
| `well-known-ingress.yaml` | `.well-known` for Matrix discovery |

## Post-deploy checks

```bash
flux get helmrelease element-server-suite -n communication
kubectl get pods -n communication
kubectl get cluster -n communication  # CNPG
```

Create the first admin user via your registration flow after DNS and certificates are ready.

## Security notes

- Use strong unique DB passwords; keep `ELEMENT_REGISTRATION_SECRET` out of Git plaintext.
- Federation is restricted in chart values (`send_federation` / `receive_federation` false) for a private homeserver.
- Review rate limiting and auth in Synapse/MAS as you harden the deployment.
