---
name: domain-knowledge
description: Domain-specific knowledge for the Body Control Module (BCM) automotive domain -- typical ECUs/modules, signal/command naming conventions, vehicle networks, common requirement and test-scenario patterns, preconditions, priority/safety notes, and terminology pitfalls. This domain is fixed for the whole run; use during discovery, extraction, resolution, merge planning, and drafting whenever requirement text, a sheet name, or a signal/command name uses BCM-specific terminology that isn't immediately clear.
---

# Domain Knowledge: BCM (Body Control Module)

Body electronics and comfort/convenience features -- everything a driver
touches that isn't propulsion, braking/steering, or infotainment. Use this
to recognize domain terminology faster; it never substitutes for actually
finding a signal/command in a supporting document during resolution.

## Scope

Central locking, door/window control, lighting (interior/exterior), wipers
and washers, mirrors, seats (position/heating/memory), sunroof, anti-theft
alarm, immobilizer, remote keyless entry (RKE) / passive entry-passive
start (PEPS), child locks, trunk/liftgate release.

## Typical ECUs / modules

- **BCM** -- the central body controller; usually the hub other body
  modules report through.
- **Door Control Module (DCM/DDM)** -- one per door, drives lock actuator,
  window motor, mirror, sometimes puddle lamp.
- **RKE/PEPS receiver** -- key fob RF reception, sometimes integrated into
  the BCM rather than a separate ECU.
- **Immobilizer ECU** -- may be standalone or folded into the BCM;
  interacts with the engine ECU to inhibit cranking.
- **Seat control module** -- position/memory/heating, mostly on higher
  trims.
- **Rain/light sensor module** -- feeds the BCM for auto-wiper/auto-lamp
  logic; may be a discrete sensor or bundled in the mirror/windshield
  module.

## Common signal & command categories

Expect names built around a component + action, e.g.:
`DoorLockCmd` / `DoorLockStatus`, `CentralLockCmd`, `ChildLockCmd`,
`WindowPositionCmd` / `WindowPositionStatus`, `WiperSpeedCmd`,
`WasherPumpCmd`, `HeadlampCmd` / `HeadlampStatus`, `IndicatorCmd`,
`HazardCmd`, `HornCmd`, `SeatHeaterCmd`, `MirrorFoldCmd`,
`TrunkReleaseCmd`, `AlarmArmCmd` / `AlarmStatus`, `KeyFobBatteryStatus`,
`RainSensorLevel`, `AmbientLightLevel`.

Per-door/per-corner signals are common (FL/FR/RL/RR suffixes) -- don't
assume a single global lock/window signal covers all doors; check whether
the sheet exposes one alias per door or one aggregate alias with a
position parameter.

## Vehicle networks

Primarily CAN for the body network, with LIN sub-buses off the BCM/door
modules driving individual actuators (window motors, mirror motors, seat
motors, wiper motor) -- a requirement about "the wiper motor" may resolve
through a LIN-side command list rather than the main body CAN list.

## Typical requirement & test-scenario themes

- Speed-based auto-lock / crash-based auto-unlock.
- Auto headlamp on ambient-light threshold, follow-me-home lighting delay.
- Intermittent/variable wiper speed driven by rain-sensor level.
- Power window auto-up/down with anti-pinch (obstacle) detection.
- Central locking triggered by RKE/key-fob range or PEPS proximity.
- Theft alarm arm/disarm sequencing, including delayed/perimeter modes.
- Immobilizer crank-inhibit when an unrecognized key is presented.

## Common preconditions

Ignition state (OFF/ACC/ON/CRANK), vehicle speed threshold, door
open/closed state, key-in/key-out or fob-in-range, 12V battery voltage
level (some comfort features are suppressed at low voltage).

## Priority / safety notes

Anti-pinch window behavior is frequently safety-relevant (often a higher
priority/ASIL tier than plain comfort features). Immobilizer and
alarm/anti-theft behavior is security-relevant even when not
functional-safety-critical -- treat as at least Medium-High priority by
default unless the source document states otherwise.

## Terminology pitfalls during resolution

- **"Lock" vs "Central Lock" vs "Deadlock"** -- deadlock/double-lock is a
  distinct, stronger state from a plain single-point lock; don't conflate
  the aliases.
- **Latch state vs lock state** -- a door can be latched (physically shut)
  independent of being locked; requirements sometimes test one without the
  other.
- **RKE vs PEPS** -- related but distinct feature sets (RKE = button-press
  remote; PEPS = proximity-based passive entry/start); a signal named for
  one may not apply to the other even on the same vehicle.
