# Cloudflare Tunnel Setup Guide (Permanent Named Tunnel)

This guide covers setting up a permanent, named Cloudflare Tunnel on macOS to expose local services (like localhost:8000) via a custom subdomain on your Cloudflare-managed domain.

## Current Production Setup

**Tunnel Name:** `voice-noob-dev`
**Tunnel UUID:** `697a5b0f-5432-4e27-8d6b-e08527412568`
**Domain:** `growthsystems.ai`

| Hostname | Local Service | Port |
|----------|---------------|------|
| voice-noob-api.growthsystems.ai | Backend API | 8000 |
| voice-noob-app.growthsystems.ai | Frontend | 8001 |
| floe-dev-api.growthsystems.ai | Floe API | 8787 |
| cfw-backend-api.growthsystems.ai | CFW Backend | 8085 |
| cfw-ghl-oauth-callback.growthsystems.ai | GHL OAuth | 8080 |

---

## Quick Start: Adding a New Tunnel (30 seconds)

If you already have the service running, adding a new subdomain is simple:

```bash
# 1. Edit system config
sudo nano /etc/cloudflared/config.yml

# 2. Add your new hostname (before the catch-all rule):
#   - hostname: new-app.growthsystems.ai
#     service: http://localhost:3001

# 3. Add DNS route
cloudflared tunnel route dns voice-noob-dev new-app.growthsystems.ai

# 4. Restart service
sudo launchctl stop com.cloudflare.cloudflared
sudo launchctl start com.cloudflare.cloudflared

# 5. Test it
curl https://new-app.growthsystems.ai
```

---

## Full Setup Guide (First Time Only)

### Prerequisites

- Domain already added to Cloudflare (nameservers pointing to Cloudflare)
- Cloudflare account with access to the domain
- macOS with Homebrew installed

### Step 1: Install cloudflared

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared --version
```

### Step 2: Authenticate with Cloudflare

```bash
cloudflared tunnel login
```

This will:
1. Open a browser window
2. Prompt you to log in to your Cloudflare account
3. Ask you to select the domain you want to use
4. Generate a certificate file at `~/.cloudflared/cert.pem`

### Step 3: Create a Named Tunnel

```bash
cloudflared tunnel create voice-noob-dev
```

Note the **UUID** from the output - you'll need it for the config file.

Verify:
```bash
cloudflared tunnel list
```

### Step 4: Create Configuration File

Create `~/.cloudflared/config.yaml`:

```yaml
tunnel: 697a5b0f-5432-4e27-8d6b-e08527412568
credentials-file: /Users/vasanth/.cloudflared/697a5b0f-5432-4e27-8d6b-e08527412568.json

ingress:
  - hostname: voice-noob-api.growthsystems.ai
    service: http://localhost:8000
  - hostname: voice-noob-app.growthsystems.ai
    service: http://localhost:8001
  - service: http_status:404
```

**Important:** The catch-all `- service: http_status:404` must be LAST.

### Step 5: Create DNS Records

```bash
cloudflared tunnel route dns voice-noob-dev voice-noob-api.growthsystems.ai
cloudflared tunnel route dns voice-noob-dev voice-noob-app.growthsystems.ai
```

### Step 6: Test Manually

```bash
cloudflared tunnel run voice-noob-dev
```

Test in another terminal:
```bash
curl https://voice-noob-api.growthsystems.ai/health
```

---

## Setting Up Permanent Service (IMPORTANT)

The default `cloudflared service install` is **buggy** and doesn't include the `tunnel run` command. Follow these steps instead:

### Step 1: Copy Config to System Location

```bash
sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/config.yaml /etc/cloudflared/config.yml
sudo cp ~/.cloudflared/*.json /etc/cloudflared/
sudo cp ~/.cloudflared/cert.pem /etc/cloudflared/
```

### Step 2: Update Credentials Path in System Config

```bash
sudo nano /etc/cloudflared/config.yml
```

Change the credentials path from `/Users/vasanth/.cloudflared/` to `/etc/cloudflared/`:

```yaml
tunnel: 697a5b0f-5432-4e27-8d6b-e08527412568
credentials-file: /etc/cloudflared/697a5b0f-5432-4e27-8d6b-e08527412568.json

ingress:
  - hostname: voice-noob-api.growthsystems.ai
    service: http://localhost:8000
  # ... rest of ingress rules
  - service: http_status:404
```

### Step 3: Create the Correct Launch Daemon

The default `service install` creates a broken plist. Create the correct one:

```bash
sudo tee /Library/LaunchDaemons/com.cloudflare.cloudflared.plist > /dev/null << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cloudflare.cloudflared</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/homebrew/bin/cloudflared</string>
        <string>tunnel</string>
        <string>--config</string>
        <string>/etc/cloudflared/config.yml</string>
        <string>run</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Library/Logs/com.cloudflare.cloudflared.out.log</string>
    <key>StandardErrorPath</key>
    <string>/Library/Logs/com.cloudflare.cloudflared.err.log</string>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
EOF
```

**Note:** If the heredoc doesn't work in your terminal, create the file at `/tmp/cloudflared.plist` first, then:
```bash
sudo cp /tmp/cloudflared.plist /Library/LaunchDaemons/com.cloudflare.cloudflared.plist
```

### Step 4: Load and Start the Service

```bash
sudo launchctl load /Library/LaunchDaemons/com.cloudflare.cloudflared.plist
sudo launchctl start com.cloudflare.cloudflared
```

### Step 5: Verify It's Running

```bash
# Check service status
sudo launchctl list | grep cloudflare

# Check logs
tail -f /Library/Logs/com.cloudflare.cloudflared.err.log

# Test endpoint
curl https://voice-noob-api.growthsystems.ai/health
```

---

## Managing the Service

```bash
# Stop
sudo launchctl stop com.cloudflare.cloudflared

# Start
sudo launchctl start com.cloudflare.cloudflared

# Restart (after config changes)
sudo launchctl stop com.cloudflare.cloudflared && sudo launchctl start com.cloudflare.cloudflared

# Unload completely
sudo launchctl unload /Library/LaunchDaemons/com.cloudflare.cloudflared.plist

# Reload
sudo launchctl load /Library/LaunchDaemons/com.cloudflare.cloudflared.plist
```

---

## Quick Reference Commands

```bash
# List all tunnels
cloudflared tunnel list

# Get tunnel info
cloudflared tunnel info voice-noob-dev

# Delete a tunnel (stop service first)
cloudflared tunnel delete voice-noob-dev

# Validate config file
cloudflared tunnel ingress validate

# Test which service handles a URL
cloudflared tunnel ingress rule https://voice-noob-api.growthsystems.ai

# View logs
tail -f /Library/Logs/com.cloudflare.cloudflared.err.log
tail -f /Library/Logs/com.cloudflare.cloudflared.out.log
```

---

## Troubleshooting

### Error 1033: Tunnel not running
The DNS record exists but no tunnel is connected.

**Fix:**
```bash
# Check if service is running
sudo launchctl list | grep cloudflare

# If not, start it
sudo launchctl start com.cloudflare.cloudflared

# Check logs for errors
tail -20 /Library/Logs/com.cloudflare.cloudflared.err.log
```

### Error 502: Bad Gateway
Tunnel is running but can't reach your local service.

**Fix:**
1. Verify local service is running: `curl http://localhost:8000/health`
2. Check the port in `/etc/cloudflared/config.yml` matches your service
3. May be a timing issue - wait a few seconds and retry

### "No ingress rules were defined"
Config file is missing or not being read.

**Fix:**
```bash
# Check config exists and is valid
cat /etc/cloudflared/config.yml

# Verify plist has --config argument
cat /Library/LaunchDaemons/com.cloudflare.cloudflared.plist | grep -A5 ProgramArguments
```

### DNS record already exists
When adding a new route and a CNAME/A record already exists.

**Fix:**
1. Go to Cloudflare Dashboard > DNS > Records
2. Delete the existing record for that subdomain
3. Re-run: `cloudflared tunnel route dns voice-noob-dev subdomain.domain.com`

### Service not starting after reboot
The plist might be corrupted or have wrong permissions.

**Fix:**
```bash
sudo chmod 644 /Library/LaunchDaemons/com.cloudflare.cloudflared.plist
sudo chown root:wheel /Library/LaunchDaemons/com.cloudflare.cloudflared.plist
sudo launchctl load /Library/LaunchDaemons/com.cloudflare.cloudflared.plist
```

---

## Security Notes

| Component | Location | Secret? |
|-----------|----------|---------|
| UUID | In DNS records (public) | No |
| credentials JSON | `/etc/cloudflared/*.json` | **YES** |
| cert.pem | `/etc/cloudflared/cert.pem` | **YES** |

**Never commit credentials files to git!**

The UUID is visible in your DNS CNAME records and that's fine - security comes from the credentials file, not the UUID.

---

## File Locations

| File | Purpose |
|------|---------|
| `~/.cloudflared/cert.pem` | Account authentication (from login) |
| `~/.cloudflared/<UUID>.json` | Tunnel credentials |
| `~/.cloudflared/config.yaml` | User config (for manual runs) |
| `/etc/cloudflared/config.yml` | System service config |
| `/etc/cloudflared/<UUID>.json` | System credentials copy |
| `/Library/LaunchDaemons/com.cloudflare.cloudflared.plist` | Service definition |
| `/Library/Logs/com.cloudflare.cloudflared.*.log` | Service logs |

---

## Sources

- [Create a locally-managed tunnel - Cloudflare Docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/create-local-tunnel/)
- [Run as a service on macOS - Cloudflare Docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/local-management/as-a-service/macos/)
- [DNS records for Cloudflare Tunnel - Cloudflare Docs](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/routing-to-tunnel/dns/)
