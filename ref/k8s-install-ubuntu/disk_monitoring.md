# Host-Level Drive and ZFS Monitoring Suite

This documentation outlines the automated host-level infrastructure designed to monitor physical drive hardware (SAS/SATA) and ZFS storage pools (`hdd01` and `ssd01`) on your single-node Kubernetes cluster. 

All storage operations and physical hardware checks run directly on the host operating system to avoid security privileges, container isolation bypass issues, and dependency risks associated with Kubernetes pods.

---

## Architecture Overview

1. **Drive Hardware Monitoring**: A custom Bash script utilizing `smartctl` to intercept raw sector, lifecycle, and controller metrics from every SAS/SATA device.
2. **Real-time Event Engine**: ZFS Event Daemon (ZED) configured to send instantaneous email alerts the moment data corruption or hardware degradation is logged by the kernel.
3. **Automated Preventive Maintenance**: Cron-driven staggered data scrubs to proactively verify pool block consistency without resource competition.

---

## Part 1: Automated Storage Health Script

This script automatically discovers all active physical block storage devices, queries their SMART profiles, evaluates active ZFS pool health metrics, and sends email notifications upon anomaly detection.

### 1. Script Deployment
Create the target monitoring payload file:
```bash
sudo nano /usr/local/bin/check_drive_health.sh
```

Paste the following production script inside:

```bash
#!/usr/bin/env bash

# Configuration
ALERT_EMAIL="sylvain@nforcer.com"
HOSTNAME=$(hostname)
ALERT_TRIGGERED=0
EMAIL_BODY=""

# Ensure the script runs as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root."
  exit 1
fi

# ----------------------------------------------------
# Check #1: ZFS Pool Health
# ----------------------------------------------------
if command -v zpool &> /dev/null; then
  # Get pools that are NOT in ONLINE status
  UNHEALTHY_POOLS=$(zpool list -H -o name,health | awk '$2 != "ONLINE"')

  if [ -n "$UNHEALTHY_POOLS" ]; then
    ALERT_TRIGGERED=1
    EMAIL_BODY+=$'\n=== UNHEALTHY ZFS POOLS DETECTED ===\n'
    EMAIL_BODY+="$UNHEALTHY_POOLS"$'\n'
    EMAIL_BODY+=$'\nFull ZFS Status:\n'
    EMAIL_BODY+="$(zpool status)"$'\n'
  fi
else
  EMAIL_BODY+=$'\n[WARNING]: zpool command not found. Skipping ZFS check.\n'
fi

# ----------------------------------------------------
# Check #2: SAS / SATA SMART Health
# ----------------------------------------------------
if command -v smartctl &> /dev/null; then
  # Automatically detect all physical block devices (excluding virtual/loop/ram)
  DRIVES=$(lsblk -dno NAME,TYPE | awk '$2=="disk" {print $1}')

  for DRIVE in $DRIVES; do
    DEVICE_PATH="/dev/$DRIVE"
    
    # Run smartctl health check
    SMART_CHECK=$(smartctl -H "$DEVICE_PATH" 2>&1)
    SMART_STATUS=$?

    # smartctl returns non-zero if there is a failure or look-ahead warning
    if [ $SMART_STATUS -ne 0 ]; then
      ALERT_TRIGGERED=1
      EMAIL_BODY+=$'\n=== DRIVE FAILURE WARNING ===\n'
      EMAIL_BODY+="Device: $DEVICE_PATH"$'\n'
      EMAIL_BODY+="Result: $SMART_CHECK"$'\n'
      EMAIL_BODY+="----------------------------------------"$'\n'
    fi
  done
else
  ALERT_TRIGGERED=1
  EMAIL_BODY+=$'\n[ERROR]: smartctl command not found. Cannot check drive hardware health.\n'
fi

# ----------------------------------------------------
# Send Alert Email if Issues Found
# ----------------------------------------------------
if [ $ALERT_TRIGGERED -eq 1 ]; then
  SUBJECT="[ALERT] Hardware Drive Failure Detected on $HOSTNAME"
  
  # Try sending using 'mail' or 'sendmail'
  if command -v mail &> /dev/null; then
    echo "$EMAIL_BODY" | mail -s "$SUBJECT" "$ALERT_EMAIL"
  elif command -v sendmail &> /dev/null; then
    (
      echo "Subject: $SUBJECT"
      echo "To: $ALERT_EMAIL"
      echo ""
      echo "$EMAIL_BODY"
    ) | sendmail -t
  else
    echo "Alert triggered but no mail utilities (mail/sendmail) found to send email."
    echo "$EMAIL_BODY"
  fi
fi
```

### 2. Execution Permissions & Infrastructure Requirements
Make the script executable and install the necessary monitoring and local email engine packages:
```bash
sudo chmod +x /usr/local/bin/check_drive_health.sh
sudo apt update && sudo apt install smartmontools mailutils -y
```

### 3. Cron Automation
Configure the script to run implicitly every single hour. Open the system crontab engine:
```bash
sudo crontab -e
```
Add this rule directly at the bottom:
```text
0 * * * * /usr/local/bin/check_drive_health.sh > /dev/null 2>&1
```

---

## Part 2: Real-Time ZFS Event Daemon (ZED) Setup

While the script runs hourly, ZED catches issues immediately (e.g., IO read errors, checksum faults).

### 1. Installation
Ensure the native daemon hook is initialized on the machine:
```bash
sudo apt install zfs-zed -y
```

### 2. Parameter Tuning
Open the global configurations file:
```bash
sudo nano /etc/zfs/zed.d/zed.rc
```
Uncomment and adjust the following specific properties to tie notifications to the infrastructure engineer:
```bash
ZED_EMAIL_ADDR="sylvain@nforcer.com"
ZED_EMAIL_OPTS="-s '@SUBJECT@' @ADDRESS@"
ZED_NOTIFY_DATA=1
ZED_NOTIFY_VERBOSE=0
```

### 3. Service Lifecycle Management
Apply internal configuration adjustments, boot the engine hook, and enforce run-on-startup criteria:
```bash
sudo systemctl restart zfs-zed
sudo systemctl enable zfs-zed
```

### 4. Verification Tracking
To verify the daemon tracking pipeline or assert validation testing, use the following operational hooks:
```bash
# View active daemon tracking metrics
sudo systemctl status zfs-zed

# Force configurations reload and check kernel notification loop triggers
sudo killall -HUP zed
```

---

## Part 3: Staggered Pool Scrub Schedules

To optimize array utilization performance and prevent I/O bottlenecks across multi-drive configurations, scrubs for `ssd01` and `hdd01` are explicitly decoupled.

### 1. Automation Mapping
Open the root user cron schema file:
```bash
sudo crontab -e
```

### 2. Cron Configuration Rules
Insert these configuration directives into the table:
```text
# ZFS Pool Automation Scrubs
# Run ssd01 arrays on the 1st of every month at 02:00 AM
0 2 1 * * /sbin/zpool scrub ssd01

# Run hdd01 mechanical disk groups on the 15th of every month at 02:00 AM
0 2 15 * * /sbin/zpool scrub hdd01
```

*Note: Any array metadata corrections or bad sector reallocation workflows initialized during these cron executions will be explicitly intercepted by ZED and reported directly to your target email inbox.*

