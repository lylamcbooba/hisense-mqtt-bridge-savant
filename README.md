# Hisense 100U65QF MQTT Bridge - Installation Guide

A step-by-step guide for Savant dealers to install the Hisense TV MQTT bridge driver on a Savant Smart Host.

---

## Table of Contents

1. [What This Does](#what-this-does)
2. [What You Need Before Starting](#what-you-need-before-starting)
3. [Part 1: Network Setup](#part-1-network-setup)
4. [Part 2: Download the Client Certificates](#part-2-download-the-client-certificates)
5. [Part 3: Install the Bridge Service on the Smart Host](#part-3-install-the-bridge-service-on-the-smart-host)
6. [Part 4: Pair the Bridge with the TV](#part-4-pair-the-bridge-with-the-tv)
7. [Part 5: Install the Savant Component Profile](#part-5-install-the-savant-component-profile)
8. [Part 6: Configure in Blueprint](#part-6-configure-in-blueprint)
9. [Part 7: Verify Everything Works](#part-7-verify-everything-works)
10. [Troubleshooting](#troubleshooting)
11. [Updating the Driver](#updating-the-driver)
12. [Uninstalling](#uninstalling)

---

## What This Does

The Hisense 100U65QF TV has a built-in MQTT broker that allows network-based control (power, volume, input selection, navigation). Savant does not natively speak MQTT, so this driver installs a small bridge service on the Smart Host that translates between Savant's HTTP commands and the TV's MQTT protocol.

**The result:** The TV appears as a native device in Blueprint with full two-way control -- real-time volume feedback, power state, input status, and absolute volume control (not just up/down).

**Architecture:**

```
Savant App / Touchscreen
        |
   Savant Component Engine
        |  (HTTP on localhost)
   Bridge Service (on Smart Host)
        |  (MQTT over TLS)
   Hisense 100U65QF TV
```

---

## What You Need Before Starting

- [ ] Savant Smart Host with SSH access (Linux-based)
- [ ] Savant Blueprint installed on your Mac
- [ ] SavantOS 11.0 or later
- [ ] Python 3.8 or later on the Smart Host (check with `python3 --version` over SSH)
- [ ] Hisense 100U65QF TV on the same network as the Smart Host
- [ ] TV's MAC address (found in TV Settings > Network > About, or on a sticker on the back)
- [ ] A laptop or phone near the TV to read the PIN code during pairing
- [ ] The TV must be **powered on** during installation and pairing

---

## Part 1: Network Setup

### 1.1 Assign a Static IP (DHCP Reservation) to the TV

The TV needs a fixed IP address so the bridge can always find it. Do this in your router or DHCP server.

1. Find the TV's current IP address:
   - On the TV: **Settings > Network > Network Configuration > View network status**
   - Note the IP address and MAC address

2. In your router's admin panel, create a DHCP reservation:
   - **MAC address:** The TV's MAC (format: `AA:BB:CC:DD:EE:FF`)
   - **Reserved IP:** Choose an available static IP on your LAN (e.g., `192.168.1.50`)

3. Restart the TV's network connection (or reboot the TV) so it picks up the reservation.

4. Verify by pinging from the Smart Host:
   ```bash
   ping 192.168.1.50
   ```
   You should get replies.

### 1.2 Verify Same Network Segment

The Smart Host and TV **must be on the same VLAN / network segment**. Wake-on-LAN (used for power-on) does not work across VLANs.

If the Smart Host and TV are on different VLANs, move one of them or configure a WOL relay on your router.

---

## Part 2: Download the Client Certificates

The Hisense 100U65QF requires mutual TLS authentication. You need client certificate files from the Hisense RemoteNOW app.

1. Download the certificate archive from:
   **https://github.com/d3nd3/Hisense-mqtt-keyfiles**

   Click the green "Code" button > "Download ZIP", or clone the repo.

2. Inside the archive, find these two files:
   - `rcm_certchain_pem.cer` (client certificate)
   - `rcm_pem_privkey.pkcs8` (client private key)

   They may be inside a `hi_keys.zip` file within the repo -- extract that too.

3. Keep these files handy. You will copy them to the Smart Host in Part 3.

---

## Part 3: Install the Bridge Service on the Smart Host

### 3.1 SSH into the Smart Host

```bash
ssh savant@<smart-host-ip>
```

Replace `<smart-host-ip>` with your Smart Host's IP address. The default username is typically `savant` -- use whatever credentials your system is configured with.

### 3.2 Download the Driver Package

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

### 3.3 Copy the Certificates

Copy the certificate files you downloaded in Part 2 into the `certs/` folder:

```bash
# If you downloaded certs to your Mac:
# Run this on your Mac (not the Smart Host):
scp rcm_certchain_pem.cer savant@<smart-host-ip>:/tmp/hisense-mqtt-bridge/certs/
scp rcm_pem_privkey.pkcs8 savant@<smart-host-ip>:/tmp/hisense-mqtt-bridge/certs/
```

Or if you're already on the Smart Host and the certs are there:

```bash
cp /path/to/rcm_certchain_pem.cer /tmp/hisense-mqtt-bridge/certs/
cp /path/to/rcm_pem_privkey.pkcs8 /tmp/hisense-mqtt-bridge/certs/
```

### 3.4 Verify Certificates Are in Place

```bash
ls -la /tmp/hisense-mqtt-bridge/certs/
```

You should see:

```
rcm_certchain_pem.cer
rcm_pem_privkey.pkcs8
```

### 3.5 Run the Installer

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
TV IP address: 192.168.1.50
TV MAC address (AA:BB:CC:DD:EE:FF): AA:BB:CC:DD:EE:FF
```

Enter the static IP you set up in Part 1 and the TV's MAC address.

### 3.6 Verify the Service is Running

```bash
sudo systemctl status hisense-bridge
```

You should see `active (running)`. If it says `failed`, check the logs:

```bash
sudo journalctl -u hisense-bridge -n 50
```

---

## Part 4: Pair the Bridge with the TV

This is a one-time step. The TV needs to authorize the bridge to control it.

**The TV must be powered ON for this step.**

### 4.1 Initiate Pairing

From the Smart Host terminal:

```bash
curl -X PUT http://localhost:8642/api/auth/pair
```

You should see:

```json
{"message":"Check TV for PIN code","status":"ok"}
```

### 4.2 Read the PIN from the TV

Look at the TV screen. A 4-digit PIN code will be displayed. Write it down.

If no PIN appears:
- Make sure the TV is powered on (not in standby)
- Check the bridge logs: `sudo journalctl -u hisense-bridge -n 20`
- The bridge may not be connected yet -- wait 30 seconds and try again

### 4.3 Confirm the PIN

```bash
curl -X PUT "http://localhost:8642/api/auth/confirm?pin=1234"
```

Replace `1234` with the actual PIN shown on your TV.

You should see:

```json
{"status":"ok"}
```

### 4.4 Test the Connection

```bash
curl http://localhost:8642/api/state
```

You should see something like:

```json
{"input":"HDMI 1","mute":"OFF","power":"ON","volume":15}
```

If you see real values from the TV, pairing is successful.

### 4.5 Quick Test -- Change the Volume

```bash
curl -X PUT "http://localhost:8642/api/volume/set?value=20"
```

The TV's volume should change to 20. If it does, the bridge is working.

---

## Part 5: Install the Savant Component Profile

The component profile tells Savant how to talk to the bridge. This file goes into Blueprint on your Mac.

### 5.1 Copy the Profile to Your Mac

From your Mac terminal:

```bash
scp savant@<smart-host-ip>:/tmp/hisense-mqtt-bridge/savant/hisense_100u65qf.xml ~/Desktop/
```

Or download it directly from GitHub:
**https://github.com/lylamcbooba/hisense-mqtt-bridge/blob/main/savant/hisense_100u65qf.xml**

### 5.2 Install into Blueprint

Copy the XML file to Blueprint's component profiles directory:

```bash
cp ~/Desktop/hisense_100u65qf.xml ~/Library/Application\ Support/Savant/.SavantOS\ 11.0.6\ \(768\)/RPMInstallLink/Library/Application\ Support/RacePointMedia/systemConfig.rpmConfig/componentProfiles/
```

**Note:** The exact path depends on your SavantOS version. Look for the `componentProfiles` folder inside your current Savant installation. You can find it at:

```
~/Library/Application Support/Savant/.SavantOS <version>/RPMInstallLink/Library/Application Support/RacePointMedia/systemConfig.rpmConfig/componentProfiles/
```

### 5.3 Restart Blueprint

Close and reopen Blueprint so it picks up the new profile.

---

## Part 6: Configure in Blueprint

### 6.1 Add the TV as a Component

1. Open your Blueprint project
2. Go to the **Components** tab
3. Click **Add Component**
4. Search for manufacturer: **Hisense**, model: **100U65QF**
5. Select it and click **Add**

### 6.2 Configure the Network Connection

1. Select the newly added Hisense 100U65QF component
2. In the **Control** section, set:
   - **Connection type:** IP / Ethernet
   - **IP Address:** `127.0.0.1` (localhost -- the bridge runs on the same host)
   - **Port:** `8642`

**Important:** The IP is `127.0.0.1` (localhost), NOT the TV's IP. The Savant component engine talks to the bridge on the same host; the bridge talks to the TV.

### 6.3 Assign to a Room

1. Drag the component into the appropriate room
2. Configure the HDMI inputs to match your physical connections:
   - **HDMI 1 (eARC):** Typically the soundbar or AVR
   - **HDMI 2-4:** Your sources (Apple TV, cable box, game console, etc.)
3. Connect the media paths in Blueprint's wiring view

### 6.4 Deploy to Host

1. Click **Deploy** in Blueprint
2. Select your Smart Host
3. Deploy the configuration

---

## Part 7: Verify Everything Works

### 7.1 Test from the Savant App

1. Open the Savant app on an iPad or iPhone
2. Navigate to the room with the TV
3. Test each function:

| Function | What to Test | Expected Result |
|----------|-------------|-----------------|
| Power On | Tap power button when TV is off | TV turns on (may take 10-15 seconds) |
| Power Off | Tap power button when TV is on | TV turns off |
| Volume Up/Down | Use the volume slider or buttons | TV volume changes, slider reflects actual level |
| Mute | Tap mute button | TV mutes/unmutes |
| Input Switch | Select a different source | TV switches to that HDMI input |
| Navigation | Use the arrow pad (if visible) | TV responds to up/down/left/right/OK |

### 7.2 Test from the Command Line (Optional)

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

# Set volume to 25
curl -X PUT "http://localhost:8642/api/volume/set?value=25"

# Switch to HDMI 2
curl -X PUT "http://localhost:8642/api/input/select?source=HDMI2"

# Navigate up
curl -X PUT http://localhost:8642/api/nav/up

# Press OK
curl -X PUT http://localhost:8642/api/nav/ok
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
- Missing certificates: check `/opt/hisense-bridge/certs/` has both `.cer` and `.pkcs8` files
- Port 8642 already in use: `sudo ss -tlnp | grep 8642`

### Bridge starts but can't connect to TV

```bash
curl http://localhost:8642/api/health
```

If `tv_connected` is `false`:
- Verify TV is powered on (not standby)
- Ping the TV: `ping <tv-ip>`
- Check the TV IP in config: `sudo cat /opt/hisense-bridge/config.json`
- Verify port 36669 is reachable: `nc -zv <tv-ip> 36669`
- Check logs for TLS errors: `sudo journalctl -u hisense-bridge -n 50`

### Pairing fails / no PIN appears on TV

- The TV must be fully booted (not in standby)
- Try power cycling the TV completely (unplug for 10 seconds)
- Some TVs only show the PIN for 30 seconds -- be ready to read it quickly
- If the bridge was previously paired and the TV was factory reset, you need to re-pair

### Commands work from curl but not from Savant

- Verify Blueprint has the IP set to `127.0.0.1` port `8642` (not the TV's IP)
- Check that you deployed the configuration to the host
- Verify the component profile is in the correct `componentProfiles` directory
- Restart the Savant services on the host: `sudo systemctl restart rpmservice`

### Volume slider doesn't reflect actual TV volume

- The bridge polls state every 10 seconds. There may be a brief delay.
- If state never updates, check that `response_required` is set to `yes` in the GetState action of the XML profile. (It should be if you downloaded the latest version.)

### Power On doesn't work

- Wake-on-LAN requires the TV and Smart Host to be on the **same VLAN**
- Check the MAC address is correct in config: `sudo cat /opt/hisense-bridge/config.json`
- Some TVs need WOL enabled in settings: **Settings > Network > Wake on LAN > On**
- Power On typically takes 10-15 seconds -- the TV needs to boot before MQTT is available

### Input switching returns "Source map not available"

The bridge hasn't learned the TV's source IDs yet. This happens automatically when the TV is first connected. If it persists:

1. Make sure the TV is powered on
2. Wait for the bridge to connect (check `curl http://localhost:8642/api/health`)
3. The source map is queried automatically on connect
4. You can also manually configure it in `/opt/hisense-bridge/config.json`:
   ```json
   "source_map": {
     "HDMI1": "0",
     "HDMI2": "1",
     "HDMI3": "2",
     "HDMI4": "3",
     "Apps": "4"
   }
   ```
   Then restart: `sudo systemctl restart hisense-bridge`

   **Note:** Source IDs vary by TV. The numbers above are examples. Use `curl http://localhost:8642/api/input/list` to see the actual mapping once the TV has been connected.

---

## Updating the Driver

To update to a newer version:

```bash
cd /tmp
rm -rf hisense-mqtt-bridge
git clone https://github.com/lylamcbooba/hisense-mqtt-bridge.git
cd hisense-mqtt-bridge

# Copy existing certs back in
sudo cp /opt/hisense-bridge/certs/* certs/

# Re-run installer (preserves existing config.json)
sudo bash deploy/install.sh
```

Your configuration and pairing token are preserved -- you do not need to re-pair.

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
- **Hisense MQTT protocol reference:** https://github.com/Krazy998/mqtt-hisensetv
- **Client certificates:** https://github.com/d3nd3/Hisense-mqtt-keyfiles
