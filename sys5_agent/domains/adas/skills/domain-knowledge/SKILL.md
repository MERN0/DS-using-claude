---
name: domain-knowledge
description: Domain-specific knowledge for the Advanced Driver Assistance Systems (ADAS) automotive domain -- typical ECUs/modules, signal/command naming conventions, vehicle networks, common requirement and test-scenario patterns, preconditions, priority/safety notes, and terminology pitfalls. This domain is fixed for the whole run; use during discovery, extraction, resolution, merge planning, and drafting whenever requirement text, a sheet name, or a signal/command name uses ADAS-specific terminology that isn't immediately clear.
---

# Domain Knowledge: ADAS (Advanced Driver Assistance Systems)

Camera/radar/ultrasonic-based driver assistance and active safety
features. Use this to recognize domain terminology faster; it never
substitutes for actually finding a signal/command in a supporting document
during resolution.

## Scope

Adaptive cruise control (ACC), automatic emergency braking (AEB), lane
keep assist (LKA) / lane departure warning (LDW), blind spot detection
(BSD), forward collision warning (FCW), parking assist / automated
parking, surround-view cameras, traffic sign recognition, driver
monitoring system (DMS), highway/traffic-jam assist.

## Typical ECUs / modules

- **ADAS domain controller / ECU** -- central fusion and decision module
  on platforms with sensor fusion; on simpler platforms each sensor ECU
  may act more independently.
- **Front radar ECU** -- primary sensor for ACC/AEB/FCW longitudinal
  detection.
- **Front camera ECU** -- lane markings, traffic signs, some object
  classification.
- **Surround-view camera controller** -- parking assist, 360-degree view.
- **Ultrasonic parking sensor controller** -- short-range parking
  proximity.
- **Driver monitoring camera module** -- attention/drowsiness detection.
- Interfaces to **EPS** (steering assist actuation) and the **braking
  system** (AEB actuation) live in the chassis domain but are commonly
  referenced from ADAS requirements -- expect cross-domain signal
  references.

## Common signal & command categories

Expect names like: `ACCSetSpeedCmd` / `ACCStatus`, `FollowDistanceCmd`,
`AEBActivateCmd` / `AEBStatus`, `LKAAssistTorqueCmd` / `LKAStatus`,
`LDWWarningStatus`, `BSDWarningStatus` (often per side, left/right),
`FCWWarningStatus`, `ParkAssistEngageCmd` / `ParkAssistStatus`,
`ObjectDetectedStatus` (fused sensor output), `DriverAttentionStatus`
(DMS), `TrafficSignDetectedValue`, `SteeringTorqueOverrideStatus` (driver
override detection), `SensorBlockedStatus` (camera/radar occlusion
fault).

## Vehicle networks

High-speed CAN-FD or Automotive Ethernet, with Ethernet increasingly used
for the high-bandwidth camera/radar sensor-fusion backbone on newer
platforms; ADAS interfaces to EPS/braking typically ride the vehicle CAN.

## Typical requirement & test-scenario themes

- Activation/deactivation conditions (speed range, lane-marking
  visibility, driver-enabled state).
- Warning vs intervention thresholds (e.g. time-to-collision-based
  staging).
- Driver-override handling -- e.g. applied steering torque disengaging
  LKA, brake pedal disengaging ACC.
- Sensor degradation / fault fallback behavior (occluded camera, radar
  blockage).
- False-positive suppression scenarios.
- System state transitions: Standby / Active / Fault / Override.
- Calibration/alignment fault handling.

## Common preconditions

Vehicle speed within the feature's operational range, sensor
cleanliness/visibility status, feature enabled by the driver (button or
menu setting), and for some features a specific road-type assumption
(e.g. highway-only operation) -- confirm whether the requirement actually
states this constraint rather than assuming it.

## Priority / safety notes

Virtually all ADAS requirements should default to Critical/high-priority
given their direct role in collision avoidance -- this domain typically
carries the highest concentration of Critical-priority test cases of any
domain in this pipeline. Expect (and don't shortcut) fault-injection and
degraded-mode/fallback scenarios; these are not optional edge cases here.

## Terminology pitfalls during resolution

- **"Warning" vs "Intervention"** -- distinct severity levels (e.g. FCW
  warns, AEB intervenes); don't resolve a warning-only requirement against
  an intervention signal or vice versa.
- **"Object" vs "Target" vs "Obstacle"** -- different sensor-fusion
  suppliers use different terms for the same underlying detection concept;
  check the supporting document's own vocabulary rather than assuming
  synonymy.
- **ACC tiers are distinct features** -- plain ACC, "Full-Speed-Range ACC"
  (works down to a stop), and "Traffic Jam Assist" are related but
  functionally different feature tiers with their own signals; don't
  conflate them even when a requirement casually says "cruise control."
