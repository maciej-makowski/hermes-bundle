---
name: hermes-container-restart-mechanism
description: A mechanism for restarting the Hermes container from within the container
version: 1.0.0
author: Hermes Agent
license: MIT
---

# Hermes Container Restart Mechanism

This skill describes how to implement a restart mechanism that allows the Hermes container to signal the host system to restart its own quadlet service.

**Reality check.** On the host the gateway runs as the systemd user unit `hermes-gateway`, and the sandbox is a separate podman container the gateway creates. The agent session runs inside the gateway process, so a restart issued from a session tool call is gate-blocked: it would SIGTERM the gateway and every child mid-command. Restart from a host-side unit or timer, or hand the operator `hermes gateway restart` (equivalently `systemctl --user restart hermes-gateway`). The file-signal monitor below describes an older quadlet deployment; verify the unit names on the host before using it.

## Architecture Overview

The system uses podman quadlets managed by systemd. The container runs in an isolated environment but needs to be able to request restarts from the host.

## Solution Approach

We'll implement a file-based signaling mechanism:

1. **Signal File**: The container creates a signal file when it wants to restart
2. **Host Monitor**: A script on the host monitors for this signal and performs the restart
3. **Cleanup**: Signal file is removed after restart

## Implementation Steps

### 1. Container Side (Within the Container)

Create a restart script inside the container:

```bash
#!/bin/bash
# Create signal file to request restart
echo "Restart requested at $(date)" > /opt/data/.hermes/restart-requested
chmod 644 /opt/data/.hermes/restart-requested

# Optionally send notification to user or log
echo "Restart signal sent" >&2
```

### 2. Host Side (On the Raspberry Pi)

Create a monitoring script that watches for restart requests:

```bash
#!/bin/bash
# File: ~/restart-monitor.sh

WATCH_DIR="$HOME/.hermes"
SIGNAL_FILE="$WATCH_DIR/restart-requested"

while true; do
    if [ -f "$SIGNAL_FILE" ]; then
        echo "Restart signal detected at $(date)"
        
        # Perform restart of the hermes container service
        systemctl --user restart hermes.container
        
        # Remove the signal file after processing
        rm -f "$SIGNAL_FILE"
        
        echo "Container restarted successfully"
    fi
    
    sleep 5
done
```

### 3. Setup Instructions

1. **Create the monitoring script on the host**:
   ```bash
   cat > ~/restart-monitor.sh << 'EOF'
   #!/bin/bash
   WATCH_DIR="$HOME/.hermes"
   SIGNAL_FILE="$WATCH_DIR/restart-requested"

   while true; do
       if [ -f "$SIGNAL_FILE" ]; then
           echo "Restart signal detected at $(date)"
           
           # Perform restart of the hermes container service
           systemctl --user restart hermes.container
           
           # Remove the signal file after processing
           rm -f "$SIGNAL_FILE"
           
           echo "Container restarted successfully"
       fi
       
       sleep 5
   done
   EOF

   chmod +x ~/restart-monitor.sh
   ```

2. **Make the monitoring script run in background**:
   ```bash
   # Run as a background process
   nohup ~/restart-monitor.sh > ~/restart-monitor.log 2>&1 &
   ```

3. **Or set it up as a systemd service**:
   ```bash
   cat > ~/.config/systemd/user/restart-monitor.service << EOF
   [Unit]
   Description=Hermes Container Restart Monitor
   After=network.target

   [Service]
   Type=simple
   ExecStart=/home/cfiet-hermes/restart-monitor.sh
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=default.target
   EOF

   systemctl --user enable restart-monitor.service
   systemctl --user start restart-monitor.service
   ```

### 4. Usage from Within Container

To trigger a restart from inside the container:
```bash
# Execute the restart signal command
echo "Restart requested" > /opt/data/.hermes/restart-requested
```

## Security Considerations

1. **File Permissions**: The signal file should be world-readable but only writable by the Hermes user
2. **Validation**: The monitor script should validate that the signal is legitimate
3. **Rate Limiting**: Prevent rapid restart loops

## Alternative Approach (More Robust)

For a more robust approach, we could also implement a HTTP endpoint or use a message queue system, but the file-based approach works well for this specific setup.

## Benefits

- Allows container to request restart without direct host access
- Maintains security boundaries 
- Uses existing infrastructure (file system permissions)
- Provides logging and monitoring capabilities
- Simple and reliable implementation