# Element Matrix Server Suite Configuration
# 
# This file contains the environment variables needed for Element deployment.
# Add these variables to your clusterenv.yaml file in the clusters/main/ directory.
#
# Required Environment Variables:
# ==============================

# Domain Configuration
ELEMENT_DOMAIN=matrix.yourdomain.com

# Database Configuration
ELEMENT_DB_ROOT_PASSWORD=your_secure_postgres_root_password
ELEMENT_DB_PASSWORD=your_secure_synapse_db_password

# Redis Configuration  
ELEMENT_REDIS_PASSWORD=your_secure_redis_password

# Registration Secret (generate with: openssl rand -hex 32)
ELEMENT_REGISTRATION_SECRET=your_32_character_hex_secret

# Homepage Integration (optional)
HP_ELEMENT=your_homepage_widget_key

# Advanced Configuration (for helm-release-advanced.yaml):
# ======================================================
# ELEMENT_ADMIN_EMAIL=admin@yourdomain.com
# ELEMENT_JITSI_SECRET=your_jitsi_app_secret
# ELEMENT_TURN_USERNAME=turn_user
# ELEMENT_TURN_PASSWORD=turn_password
# ELEMENT_EXTERNAL_IP=your.external.ip.address

# Setup Instructions:
# ===================
# 1. Copy the variables above to your clusterenv.yaml file
# 2. Replace all placeholder values with your actual configuration
# 3. Generate a secure registration secret using: openssl rand -hex 32
# 4. Ensure your domain DNS points to your cluster's external IP
# 5. Choose between basic (helm-release.yaml) or advanced (helm-release-advanced.yaml) deployment
# 6. Deploy the chart using FluxCD

# Deployment Options:
# ==================
# Basic Deployment (helm-release.yaml):
# - Synapse homeserver
# - Element Web client
# - PostgreSQL database
# - Redis cache
# - Basic chat functionality

# Advanced Deployment (helm-release-advanced.yaml):
# - All basic features plus:
# - Jitsi Meet video conferencing
# - Coturn TURN server for NAT traversal
# - Enhanced voice/video capabilities
# - Screen sharing support

# Post-Deployment:
# ===============
# 1. Access Element Web at: https://element.yourdomain.com
# 2. Access Synapse API at: https://matrix.yourdomain.com
# 3. Access Jitsi Meet at: https://meet.yourdomain.com (advanced only)
# 4. Create your first admin user via the registration endpoint
# 5. Configure federation and other advanced settings as needed

# Security Notes:
# ==============
# - Use strong, unique passwords for all database connections
# - Keep the registration secret secure and don't share it
# - Consider enabling additional security features like:
#   - Rate limiting
#   - IP whitelisting
#   - Advanced authentication methods
#   - Audit logging
#   - TURN server authentication (advanced deployment)
