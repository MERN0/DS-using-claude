---
name: domain-knowledge
description: Domain-specific knowledge for the In-Vehicle Infotainment (IVI) automotive domain -- typical ECUs/modules, signal/command naming conventions, vehicle networks, common requirement and test-scenario patterns, preconditions, priority/safety notes, and terminology pitfalls. This domain is fixed for the whole run; use during discovery, extraction, resolution, merge planning, and drafting whenever requirement text, a sheet name, or a signal/command name uses IVI-specific terminology that isn't immediately clear.
---

# Domain Knowledge: IVI (In-Vehicle Infotainment)

The head unit and everything feeding it: media, navigation, phone/voice,
smartphone projection, and the HMI/display layer. Use this to recognize
domain terminology faster; it never substitutes for actually finding a
signal/command in a supporting document during resolution.

## Scope

Head unit / display HMI, audio source management, Bluetooth phone/media
pairing, smartphone projection (CarPlay/Android Auto), navigation
guidance, voice assistant, USB media, rear-seat entertainment, driver
distraction lockouts on the HMI.

## Typical ECUs / modules

- **Head Unit (HU) / Infotainment ECU** -- the central display/media
  controller.
- **Cluster / Instrument Cluster (IC)** -- sometimes shares warning-lamp or
  trip-computer signals with the HU; treat as adjacent, not identical.
- **Amplifier** -- audio output stage, separate ECU on higher trims.
- **Bluetooth module** -- may be integrated into the HU or a discrete
  module; exposes per-profile connection status (see pitfalls below).
- **USB hub controller** -- media device enumeration.
- **Display/touch controller** -- capacitive touch, brightness, backlight.

## Common signal & command categories

Expect names like: `SourceSelectCmd` (Radio/USB/BT/AUX),
`VolumeCmd` / `VolumeLevel`, `BTPairCmd` / `BTConnectionStatus`,
`NavRouteCmd` / `NavGuidanceStatus`, `DisplayBrightnessCmd`,
`VoiceAssistantActivateCmd`, `USBDeviceConnectedStatus`,
`CarPlayConnectionStatus`, `AndroidAutoConnectionStatus`,
`MediaPlayPauseCmd`, `RadioStationCmd` / `RDSStatus`,
`DistractionLockoutStatus`.

## Vehicle networks

CAN/CAN-FD for vehicle-state signals (speed, gear, reverse) that gate HMI
behavior; Automotive Ethernet or MOST for high-bandwidth audio/video
backbone on higher-end platforms; Bluetooth (with distinct A2DP/HFP/AVRCP
profile connections) for phone/media; USB for wired media and wired
CarPlay/Android Auto; Wi-Fi for wireless projection.

## Typical requirement & test-scenario themes

- Audio/video source switching logic and priority (e.g. phone call
  interrupts media playback).
- Bluetooth pairing, reconnection on ignition cycle, multi-device handling.
- Volume/mute behavior tied to vehicle state (e.g. auto-mute on reverse
  camera engage, parking-sensor beep ducking).
- Navigation guidance triggering and re-route on missed turn.
- CarPlay/Android Auto connect/disconnect and source handoff.
- Driver-distraction lockouts: features disabled or simplified above a
  speed threshold (e.g. text entry, video playback while driving).

## Common preconditions

Ignition/power mode, vehicle speed (distraction-lockout threshold),
paired-device presence, USB device inserted, cellular/network availability
for online navigation or voice features, gear state (reverse for camera
interactions).

## Priority / safety notes

Driver-distraction requirements are often regulatory-driven (e.g.
guidance limiting driver interaction while in motion) and should default
to at least Medium-High priority even if the source document doesn't
explicitly tag them -- note the assumption in the QA report per the
writing-style skill's fallback rule rather than silently downgrading them.

## Terminology pitfalls during resolution

- **"Head Unit" vs "IVI system" vs "Infotainment ECU"** -- often used
  interchangeably in requirement text for the same physical module; don't
  assume they're different systems.
- **"Source" is ambiguous** -- can mean audio source or video source (rear
  entertainment); check which the requirement actually means before
  resolving a `SourceSelectCmd`-style signal.
- **Bluetooth profile status is per-profile, not global** -- "Bluetooth
  connected" in requirement text may need to resolve to a specific
  HFP-connected or A2DP-connected signal rather than one umbrella status.
