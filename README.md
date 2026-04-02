# Hisense U65QF Series - Savant IR Profile

A Savant component profile for IR control of Hisense U65QF series TVs (55", 65", 75", 85", 100" models).

---

## What This Does

This repo contains a Savant component profile (`savant/hisense_xxu65qf_ir.xml`) that controls Hisense U65QF series TVs via IR. The profile includes IR codes for power, volume, mute, navigation, input selection, channel control, media transport, and app shortcuts.

**Supported models:** Hisense 55QU65QF, 65QU65QF, 75QU65QF, 85QU65QF, 100QU65QF (and Amazon FireTV variants).

---

## What You Need

- Savant Smart Host with an IR emitter aimed at the TV's IR receiver
- Savant Blueprint installed on your Mac
- SavantOS 11.0 or later

---

## Installation

### 1. Copy the Profile to Your Mac

Download or clone this repo and copy the XML profile to your Mac:

```bash
git clone https://github.com/lylamcbooba/hisense-mqtt-bridge.git
```

### 2. Install into Blueprint

Copy the XML file to Blueprint's component profiles directory:

```bash
cp hisense-mqtt-bridge/savant/hisense_xxu65qf_ir.xml ~/Library/Application\ Support/Savant/.SavantOS\ <version>/RPMInstallLink/Library/Application\ Support/RacePointMedia/systemConfig.rpmConfig/componentProfiles/
```

**Note:** The exact path depends on your SavantOS version. Look for the `componentProfiles` folder inside your current Savant installation.

### 3. Restart Blueprint

Close and reopen Blueprint so it picks up the new profile.

### 4. Add the TV in Blueprint

1. Open your Blueprint project
2. Go to the **Components** tab
3. Click **Add Component**
4. Search for manufacturer: **Hisense**, model: **(xx)U65QF**
5. Select it and click **Add**

### 5. Configure IR Control

1. Select the Hisense component
2. In the **Control** section, set the connection type to **IR**
3. Assign the IR port that has an emitter aimed at the TV

### 6. Assign to a Room

1. Drag the component into the appropriate room
2. Configure the HDMI inputs to match your physical connections
3. Connect the media paths in Blueprint's wiring view

### 7. Deploy

Deploy the configuration to your Smart Host.

---

## Available Controls

| Category | Functions |
|----------|-----------|
| Power | On, Off, Toggle |
| Volume | Up, Down, Mute On/Off |
| Navigation | Up, Down, Left, Right, Select/OK, Menu, Home, Exit/Back |
| Input | HDMI 1-4, ANT/CABLE, AV IN, Apps, Input Next |
| Channel | Up, Down, Number 0-9, Last Channel, Guide |
| Media | Play, Pause, Stop, Rewind, Fast Forward, Scan Up/Down |
| Color Buttons | Red, Green, Blue, Yellow |
| Shapes | A (Triangle), B (Square), C (Circle), D (Diamond) |
| Apps | Netflix, Prime Video, YouTube, RakutenTV |
| Other | Subtitle, TeleText, Channel List, Audio Only, Hi-DMP, Media |

---

## Notes

- Power On/Off use a toggle IR code. The profile tracks power state to send the toggle only when needed.
- Volume is controlled via repeated IR key presses (no absolute volume set).
- Mute uses a toggle IR code; the profile tracks mute state for discrete on/off.
- IR emitter must have line-of-sight to the TV's IR receiver.
