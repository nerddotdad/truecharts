# 📽️ Watch History & Playback Data Guide

This guide shows how to find movie watching history for your Jellyfin (and other media server) apps.

---

## 🎬 Jellyfin Watching History

### Overview
- **Jellyfin instance:** `jellyfin.hoth.systems`
- **Namespace:** `media`
- **Pod:** `jellyfin-56b44757fc-lx768` (or similar pod name)
- **Status:** Running (5d23h uptime)

---

## 🔍 Method 1: Jellyfin Web UI (EASIEST)

### Access Your Dashboard
```bash
# Open your Jellyfin UI
https://jellyfin.hoth.systems

# Navigate to:
# 1. Login to your account
# 2. Go to Library → Movies
# 3. Click on "Play State & Progress" in left sidebar
# 4. Sort by "Date Watched" to see most recent
```

### API Endpoint for Recent Activity
```bash
# Access jellyfin API (port-forward if needed)
kubectl run jellyfin-api --rm --restart=Never --image=jellyfin/jellyfin:latest -- \
    bash

# Inside the container:
# http://localhost:8096/Web/index.html
# Or use the external URL directly
```

---

## 🔬 Method 2: Execute into Jellyfin Pod

### Get the Pod Name
```bash
# List jellyfin pods
kubectl get pods -n media | grep jellyfin

# Example output:
# jellyfin-56b44757fc-lx768  1/1     Running   0          5d23h
```

### Access Files Inside Container
```bash
# List /config/data directory
kubectl exec -n media <pod-name> -- bash -c "ls -la /config/data/"

# Check for database
kubectl exec -n media <pod-name> -- bash -c "ls -la /config/data/data/"

# Check playstate.dat if exists
kubectl exec -n media <pod-name> -- bash -c "ls -la /config/data/data/playstate.dat 2>/dev/null && cat /config/data/data/playstate.dat | tail -20 || echo 'Using database for playstate'"
```

### Query the Database

```bash
# If you have a SQLite database, query recent playback
kubectl exec -n media <pod-name> -- bash -c '
    cd /config/data/data/
    if [ -f jellyfin.db ]; then
        sqlite3 jellyfin.db "SELECT * FROM PlaybackProgress ORDER BY PlayProgress DESC LIMIT 10;"
    fi
'
```

### Check Config Files
```bash
# View Jellyfin config
kubectl exec -n media <pod-name> -- bash -c "ls -la /config/"

# Check for user data
kubectl exec -n media <pod-name> -- bash -c "ls -la /config/data/"

# Access media library
kubectl exec -n media <pod-name> -- bash -c "ls -la /media/"
```

---

## 📡 Method 3: Jellyfin API Calls

### Get Recently Played (via API)

```bash
# If Jellyfin exposes API, you can use it
# Replace USER_ID with your user ID (usually 0 or 1)
curl -X GET \
  -u USER:password \
  "https://jellyfin.hoth.systems/Users/USER_ID/ViewHistory" \
  -H "Accept: application/json"
```

### Get Now Playing
```bash
curl -X GET \
  -u USER:password \
  "https://jellyfin.hoth.systems/Sessions/NOW_PLAYING"
```

---

## 🎯 Method 4: Immich (For Photo/Video Watching History)

If you're also looking for video watching via Immich:

```bash
# Immich is also running in media namespace
kubectl get pods -n immich

# Access Immich
# Your Immich URL would be listed via:
kubectl get ingress -A | grep immich
```

**Immich features:**
- Media library with play history
- Playback progress tracking
- Recently viewed items

---

## 📊 Method 5: Check Activity Logs

### View Recent Activity
```bash
# Tail jellyfin logs
kubectl logs -n media jellyfin-56b44757fc-lx768 -f | grep -i "playback\|playitem\|finished"

# Search for playback events
kubectl logs -n media jellyfin-56b44757fc-lx768 -f | grep -iE "PlaybackProgress|PlayItem"
```

### Filter Playback Events
```bash
# Look for finished playback events
kubectl logs -n media jellyfin-56b44757fc-lx768 --tail=500 | grep -i ".*finished watching.*movie"

# Or look for session events  
kubectl logs -n media jellyfin-56b44757fc-lx768 --tail=1000 | grep -iE "session|playback"
```

---

## 🐳 Method 6: Using Jellyfin Client

### Recommended Tools

**JellyWatch** (Docker container for viewing stats):
- Pulls data from your Jellyfin instance
- Shows viewing history
- Library statistics
- Live session monitoring

**Jellyfin Docker Dashboard:**
- Provides detailed stats
- Playback counters
- User statistics

---

## 🎬 Finding Your Last Watched Movie

### Quick Command
```bash
# Most straightforward: Web UI
# Go to jellyfin.hoth.systems
# Check History/Resume section

# Alternative: Check the database
kubectl exec -n media <pod-name> -- bash -c '
    echo "=== Recent Playback Events ==="
    # Your database path might vary
    DB_PATH=/config/data/data/jellyfin.db
    if [ -f "$DB_PATH" ]; then
        sqlite3 "$DB_PATH" "SELECT PlaybackProgress, Name, ImageTag FROM PlaybackProgress ORDER BY PlaybackProgress DESC LIMIT 10;"
    else
        echo "Database not found at standard location. Try:"
        echo "ls -la /config/data/data/"
    fi
'
```

### Check Pod for Files
```bash
# Full filesystem access
kubectl exec -n media <pod-name> -- bash
cd /config/data/data/
ls -la
```

---

## 🔍 Troubleshooting

### No Data Found?

1. **Check if you've been watching:**
```bash
kubectl logs -n media jellyfin-56b44757fc-lx768 | grep -i "watching"
```

2. **Check database initialization:**
```bash
kubectl exec -n media <pod-name> -- bash -c "ls -la /config/data/data/"
```

3. **Verify Trakt sync:**
```bash
# If using Trakt plugin, history might be in Trakt
# Access trakt.com and check your profile

# Check if Trakt plugin is enabled (in logs):
kubectl logs -n media jellyfin-56b44757fc-lx768 | grep -i "trakt"
```

### Database not found?
```bash
# Jellyfin may store playstate differently depending on version
# Common locations:
ls /config/data/data/playstate.json 2>/dev/null
ls /config/data/data/playstate.dat 2>/dev/null
ls /config/data/playstate.db 2>/dev/null
```

### Permission Issues
```bash
# Make sure you have right permissions
kubectl exec -n media <pod-name> -- whoami
kubectl exec -n media <pod-name> -- id
```

---

## 🎯 Pro Tips

### Set Up Monitoring
```bash
# Watch for recent activity
watch -n 30 'kubectl logs -n media jellyfin-56b44757fc-lx768 --tail=50 | tail -20'
```

### Enable Logging
```bash
# Add to Jellyfin HelmRelease if needed
# Configure better logging retention
# Check pod resource limits
kubectl describe pod <pod-name> -n media
```

### Archive Old Logs
```bash
# For debugging, archive logs before they disappear
kubectl logs -n media jellyfin-56b44757fc-lx768 --tail=1000 > jellyfin-activity.log
```

---

## 📝 Summary

**To find your last watched movie:**

1. **🌐 Easiest:** Visit `https://jellyfin.hoth.systems`, check History
2. **🔬 Most detailed:** Execute into `<pod-name>` pod and check `/config/data/data/`
3. **⚡ Fastest:** Use kubectl logs to search for recent playback events

**Most common locations for playstate:**
- `/config/data/data/jellyfin.db` (SQLite database)
- `/config/data/data/playstate.json` or `.dat`
- Some versions store it in the main database in a different table

---

**Last Updated:** 2026-05-22  
**Cluster:** main  
**Namespace:** media  
**App:** jellyfin
