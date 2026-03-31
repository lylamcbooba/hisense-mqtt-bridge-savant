# Hisense 100U65QF Android TV Bridge - Installation Guide

A step-by-step guide for Savant dealers to install the Hisense TV bridge driver on a Savant Smart Host.

---

## Table of Contents

1. [What This Does](#what-this-does)
2. [What You Need Before Starting](#what-you-need-before-starting)
3. [Part 1: Network Setup](#part-1-network-setup)
4. [Part 2: Install the Bridge Service on the Smart Host](#part-2-install-the-bridge-service-on-the-smart-host)
5. [Part 3: Pair the Bridge with the TV](#part-3-pair-the-bridge-with-the-tv)
6. [Part 4: Install the Savant Component Profile](#part-4-install-the-savant-component-profile)
7. [Part 5: Configure in Blueprint](#part-5-configure-in-blueprint)
8. [Part 6: Verify Everything Works](#part-6-verify-everything-works)
9. [Troubleshooting](#troubleshooting)
10. [Updating the Driver](#updating-the-driver)
11. [Uninstalling](#uninstalling)

---

## What This Does

The Hisense 100U65QF is an Android TV-based laser TV that supports the Android TV Remote v2 protocol for network control (power, volume, input selection, navigation). Savant does not natively speak this protocol, so this driver installs a small bridge service on the Smart Host that translates between Savant's HTTP commands and the TV's Android TV Remote protocol.

**The result:** The TV appears as a native device in Blueprint with full two-way control -- real-time volume feedback, power state, and input status.

**Architecture:**

```
Savant App / Touchscreen
        |
   Savant Component Engine
        |  (HTTP on localhost:8642)
   Bridge Service (on Smart Host)
        |  (Android TV Remote v2 on port 6466)
   Hisense 100U65QF TV
```

**Note:** This TV uses a Bluetooth remote and does not have an IR receiver. IR control is not available. All control is via the network.

---

## What You Need Before Starting

- [ ] Savant Smart Host with SSH access (Linux-based)
- [ ] Savant Blueprint installed on your Mac
- [ ] SavantOS 11.0 or later
- [ ] Python 3.8 or later on the Smart Host (check with `python3 --version` over SSH)
- [ ] Hisense 100U65QF TV on the same network as the Smart Host
- [ ] TV's MAC address (found in TV Settings > Network > About, or on a sticker on the back)
- [ ] A laptop or phone near the TV to read the pairing code during setup
- [ ] The TV must be **fully powered on** (not standby) during installation and pairing

---

## Part 1: Network Setup

### 1.1 Assign a Static IP (DHCP Reservation) to the TV

The TV needs a fixed IP address so the bridge can always find it. Do this in your router or DHCP server.

1. Find the TV's current IP address:
   - On the TV: **Settings > Network > Network Configuration > View network status**
   - Note the IP address and MAC address

2. In your router's admin panel, create a DHCP reservation:
   - **MAC address:** The TV's MAC (format: `AA:BB:CC:DD:EE:FF`)
   - **Reserved IP:** Choose an available static IP on your LAN (e.g., `192.168.1.125`)

3. Restart the TV's network connection (or reboot the TV) so it picks up the reservation.

4. Verify by pinging from the Smart Host:
   ```bash
   ping 192.168.1.125
   ```
   You should get replies.

### 1.2 Verify Same Network Segment

The Smart Host and TV **must be on the same VLAN / network segment**. Wake-on-LAN (used for power-on) does not work across VLANs.

If the Smart Host and TV are on different VLANs, move one of them or configure a WOL relay on your router.

### 1.3 Verify the TV's Android TV Remote Service

The TV must be advertising the Android TV Remote v2 service. You can verify from a Mac on the same network:

```bash
dns-sd -B _androidtvremote2._tcp local.
```

You should see the TV listed (e.g., "Living Room TV"). If not, the TV may need a firmware update or may not support this protocol.

---

## Part 2: Install the Bridge Service on the Smart Host

### 2.1 SSH into the Smart Host

```bash
ssh savant@<smart-host-ip>
```

Replace `<smart-host-ip>` with your Smart Host's IP address.

### 2.2 Download the Driver Package

```bash
cd /tmp
git clone https://github.com/lylamcbooba/hisense-mqtt-bridge.git
cd hisense-mqtt-bridge
```

If `git` is not available on the host, download the ZIP from GitHub on your Mac and `scp` it over:

```bash
# On your Mac:
scp -r ~/Downloads/hisense-mqtt-bridge-main savant@<smart-host-ip>:/tmp/hisense-mqtt-bridge
```

### 2.3 Run the Installer

```bash
cd /tmp/hisense-mqtt-bridge
sudo bash deploy/install.sh
```

The installer will:
1. Create a `hisense-bridge` system user
2. Copy files to `/opt/hisense-bridge/`
3. Set up a Python virtual environment and install dependencies
4. Ask you for the **TV's IP address** and **MAC address**
5. Start the bridge service

**When prompted:**

```
TV IP address: 192.168.1.125
TV MAC address (AA:BB:CC:DD:EE:FF): AA:BB:CC:DD:EE:FF
```

Enter the static IP you set up in Part 1 and the TV's MAC address.

**Note:** No certificates need to be downloaded or installed. The bridge automatically generates its own TLS certificates on first run.

### 2.4 Verify the Service is Running

```bash
sudo systemctl status hisense-bridge
```

You should see `active (running)`. If it says `failed`, check the logs:

```bash
sudo journalctl -u hisense-bridge -n 50
```

---

## Part 3: Pair the Bridge with the TV

This is a one-time step. The TV needs to authorize the bridge to control it.

**The TV must be fully powered ON (home screen visible) for this step.**

### 3.1 Initiate Pairing

From the Smart Host terminal:

```bash
curl -X PUT http://localhost:8642/api/auth/pair
```

You should see:

```json
{"message":"Check TV for pairing code","status":"ok"}
```

### 3.2 Read the Code from the TV

Look at the TV screen. A **6-character hex code** will be displayed. Write it down.

If no code appears:
- Make sure the TV is fully powered on (screen showing, not in standby)
- Check the bridge logs: `sudo journalctl -u hisense-bridge -n 20`
- Wait 30 seconds and try again

### 3.3 Confirm the Code

```bash
curl -X PUT "http://localhost:8642/api/auth/confirm?pin=A1B2C3"
```

Replace `A1B2C3` with the actual 6-character code shown on your TV.

You should see:

```json
{"status":"ok"}
```

### 3.4 Test the Connection

```bash
curl http://localhost:8642/api/state
```

You should see something like:

```json
{"input":"com.google.android.tvlauncher","mute":"OFF","power":"ON","volume":15}
```

If you see real values from the TV, pairing is successful.

### 3.5 Quick Test -- Change the Volume

```bash
curl -X PUT http://localhost:8642/api/volume/up
```

The TV's volume should increase by one step. If it does, the bridge is working.

---

## Part 4: Install the Savant Component Profile

The component profile tells Savant how to talk to the bridge. This file goes into Blueprint on your Mac.

### 4.1 Copy the Profile to Your Mac

From your Mac terminal:

```bash
scp savant@<smart-host-ip>:/tmp/hisense-mqtt-bridge/savant/hisense_100u65qf.xml ~/Desktop/
```

### 4.2 Install into Blueprint

Copy the XML file to Blueprint's component profiles directory:

```bash
cp ~/Desktop/hisense_100u65qf.xml ~/Library/Application\ Support/Savant/.SavantOS\ 11.0.6\ \(768\)/RPMInstallLink/Library/Application\ Support/RacePointMedia/systemConfig.rpmConfig/componentProfiles/
```

**Note:** The exact path depends on your SavantOS version. Look for the `componentProfiles` folder inside your current Savant installation. You can find it at:

```
~/Library/Application Support/Savant/.SavantOS <version>/RPMInstallLink/Library/Application Support/RacePointMedia/systemConfig.rpmConfig/componentProfiles/
```

### 4.3 Restart Blueprint

Close and reopen Blueprint so it picks up the new profile.

---

## Part 5: Configure in Blueprint

### 5.1 Add the TV as a Component

1. Open your Blueprint project
2. Go to the **Components** tab
3. Click **Add Component**
4. Search for manufacturer: **Hisense**, model: **100U65QF**
5. Select it and click **Add**

### 5.2 Configure the Network Connection

1. Select the newly added Hisense 100U65QF component
2. In the **Control** section, set:
   - **Connection type:** IP / Ethernet
   - **IP Address:** `127.0.0.1` (localhost -- the bridge runs on the same host)
   - **Port:** `8642`

**Important:** The IP is `127.0.0.1` (localhost), NOT the TV's IP. The Savant component engine talks to the bridge on the same host; the bridge talks to the TV.

### 5.3 Assign to a Room

1. Drag the component into the appropriate room
2. Configure the HDMI inputs to match your physical connections:
   - **HDMI 1 (eARC):** Typically the soundbar or AVR
   - **HDMI 2-4:** Your sources (Apple TV, cable box, game console, etc.)
3. Connect the media paths in Blueprint's wiring view

### 5.4 Deploy to Host

1. Click **Deploy** in Blueprint
2. Select your Smart Host
3. Deploy the configuration

---

## Part 6: Verify Everything Works

### 6.1 Test from the Savant App

1. Open the Savant app on an iPad or iPhone
2. Navigate to the room with the TV
3. Test each function:

| Function | What to Test | Expected Result |
|----------|-------------|-----------------|
| Power On | Tap power button when TV is off | TV turns on (may take 10-15 seconds via WOL) |
| Power Off | Tap power button when TV is on | TV turns off |
| Volume Up/Down | Use the volume slider or buttons | TV volume changes, slider reflects actual level |
| Mute | Tap mute button | TV mutes/unmutes |
| Input Switch | Select a different source | TV switches to that HDMI input |
| Navigation | Use the arrow pad (if visible) | TV responds to up/down/left/right/OK |

### 6.2 Test from the Command Line (Optional)

From the Smart Host:

```bash
# Check health
curl http://localhost:8642/api/health

# Get current state
curl http://localhost:8642/api/state

# Power off
curl -X PUT http://localhost:8642/api/power/off

# Power on (uses Wake-on-LAN)
curl -X PUT http://localhost:8642/api/power/on

# Volume up
curl -X PUT http://localhost:8642/api/volume/up

# Volume down
curl -X PUT http://localhost:8642/api/volume/down

# Switch to HDMI 2
curl -X PUT "http://localhost:8642/api/input/select?source=HDMI2"

# Navigate up
curl -X PUT http://localhost:8642/api/nav/up

# Press OK
curl -X PUT http://localhost:8642/api/nav/ok

# Go Home
curl -X PUT http://localhost:8642/api/nav/home
```

---

## Troubleshooting

### Bridge service won't start

```bash
sudo systemctl status hisense-bridge
sudo journalctl -u hisense-bridge -n 50
```

**Common causes:**
- Python 3 not installed: `sudo apt install python3 python3-venv`
- Port 8642 already in use: `sudo ss -tlnp | grep 8642`

### Bridge starts but can't connect to TV

```bash
curl http://localhost:8642/api/health
```

If `tv_connected` is `false`:
- Verify TV is fully powered on (not standby -- the home screen must be visible)
- Ping the TV: `ping <tv-ip>`
- Check the TV IP in config: `sudo cat /opt/hisense-bridge/config.json`
- Verify Android TV Remote port is reachable: `nc <tv-ip> 6466`
- The TV's Android TV Remote service only runs when the TV is fully on
- Check logs: `sudo journalctl -u hisense-bridge -n 50`

### Pairing fails / no code appears on TV

- The TV must be fully booted with the home screen visible (not in standby)
- Try power cycling the TV completely (unplug for 10 seconds)
- The code is displayed for a limited time -- be ready to read it quickly
- If the bridge was previously paired and the TV was factory reset, delete the certs and re-pair:
  ```bash
  sudo rm /opt/hisense-bridge/certs/cert.pem /opt/hisense-bridge/certs/key.pem
  sudo systemctl restart hisense-bridge
  ```

### "InvalidAuth" in logs

The bridge needs to be paired (or re-paired) with the TV. Follow [Part 3](#part-3-pair-the-bridge-with-the-tv).

### Commands work from curl but not from Savant

- Verify Blueprint has the IP set to `127.0.0.1` port `8642` (not the TV's IP)
- Check that you deployed the configuration to the host
- Verify the component profile is in the correct `componentProfiles` directory
- Restart the Savant services on the host: `sudo systemctl restart rpmservice`

### Volume slider doesn't reflect actual TV volume

- Volume state is pushed from the TV via callbacks. There should be minimal delay.
- If state never updates, check that the bridge is connected: `curl http://localhost:8642/api/health`

### Power On doesn't work

- Wake-on-LAN requires the TV and Smart Host to be on the **same VLAN**
- Check the MAC address is correct in config: `sudo cat /opt/hisense-bridge/config.json`
- The TV may need network standby enabled in settings
- Power On typically takes 10-15 seconds -- the TV needs to boot before the bridge can reconnect

### Input switching doesn't work

The default source map uses Android TV HDMI key codes. If these don't work on your TV model, you can customize the key codes in the config:

```bash
sudo nano /opt/hisense-bridge/config.json
```

Edit the `source_map` section. The available inputs and their key codes can vary by TV model. After editing, restart:

```bash
sudo systemctl restart hisense-bridge
```

---

## Updating the Driver

To update to a newer version:

```bash
cd /tmp
rm -rf hisense-mqtt-bridge
git clone https://github.com/lylamcbooba/hisense-mqtt-bridge.git
cd hisense-mqtt-bridge

# Re-run installer (preserves existing config.json and pairing certs)
sudo bash deploy/install.sh
```

Your configuration and pairing are preserved -- you do not need to re-pair.

---

## Uninstalling

To completely remove the bridge:

```bash
# Stop and disable the service
sudo systemctl stop hisense-bridge
sudo systemctl disable hisense-bridge
sudo rm /etc/systemd/system/hisense-bridge.service
sudo systemctl daemon-reload

# Remove the installation
sudo rm -rf /opt/hisense-bridge

# Remove the service user
sudo userdel hisense-bridge
```

Then remove `hisense_100u65qf.xml` from Blueprint's `componentProfiles` directory and remove the component from your Blueprint project.

---

## Support

- **Driver source code:** https://github.com/lylamcbooba/hisense-mqtt-bridge
- **Android TV Remote v2 protocol:** https://github.com/tronikos/androidtvremote2
