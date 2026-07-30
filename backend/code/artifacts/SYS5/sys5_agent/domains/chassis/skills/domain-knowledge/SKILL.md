---
name: domain-knowledge
description: Domain-specific knowledge for the Chassis & vehicle dynamics automotive domain (braking, steering, suspension, stability control) -- typical ECUs/modules, signal/command naming conventions, vehicle networks, common requirement and test-scenario patterns, preconditions, priority/safety notes, and terminology pitfalls. This domain is fixed for the whole run; use during discovery, extraction, resolution, merge planning, and drafting whenever requirement text, a sheet name, or a signal/command name uses chassis-specific terminology that isn't immediately clear. Also matches the common misspelling "chasis".
---

# Domain Knowledge: Chassis (braking, steering, suspension, vehicle dynamics)

Braking, steering, suspension, and stability-control systems -- the
domain most directly responsible for how the vehicle physically responds
to driver and ADAS inputs. Use this to recognize domain terminology
faster; it never substitutes for actually finding a signal/command in a
supporting document during resolution.

## Scope

ABS (anti-lock braking), ESC/ESP (electronic stability control), traction
control (TCS), electric power steering (EPS), adaptive/air suspension,
tire pressure monitoring (TPMS), electronic parking brake (EPB),
brake-by-wire, active roll control, ride-height control.

## Typical ECUs / modules

- **ABS/ESC Control Unit** -- often a combined hydraulic control unit
  (HCU/ESC module) handling ABS, ESC, and TCS together.
- **EPS ECU** -- steering assist torque control.
- **Suspension Control Module** -- adaptive damping / air suspension,
  usually per-corner actuation.
- **TPMS receiver module** -- per-wheel tire pressure sensor reception.
- **EPB Control Module** -- electronic parking brake actuation.
- **Brake Booster / iBooster controller** -- brake-by-wire boost systems
  on newer platforms.

## Common signal & command categories

Expect per-wheel/per-corner naming (FL/FR/RL/RR) far more than in other
domains: `WheelSpeedValue` (per wheel), `ABSActivateStatus`,
`ESCInterventionStatus`, `TCSActivateStatus`, `BrakePressureValue` /
`BrakePressureCmd`, `SteeringAngleValue`, `SteeringAssistTorqueCmd`,
`SuspensionDamperCmd` / `SuspensionDamperStatus` (per corner),
`RideHeightCmd` / `RideHeightStatus`, `TPMSTirePressureValue` (per
wheel) / `TPMSWarningStatus`, `EPBApplyCmd` / `EPBStatus`,
`YawRateValue`, `LateralAccelValue`.

## Vehicle networks

High-speed CAN/CAN-FD chassis segment -- often the most latency-sensitive
bus in the vehicle given real-time control-loop requirements; some
platforms use FlexRay specifically for deterministic timing on
brake-by-wire or steer-by-wire systems. Confirm bus assignment via the
communication matrix rather than assuming plain CAN for every signal.

## Typical requirement & test-scenario themes

- ABS activation on wheel-slip detection.
- ESC intervention on yaw-rate/lateral-acceleration deviation from
  driver-intended path.
- TCS torque-reduction request on drive-wheel slip.
- EPS assist-curve behavior vs vehicle speed (more assist at low speed,
  less at high speed).
- EPB auto-apply on park selection or ignition-off.
- TPMS low-pressure warning thresholds and fast-leak detection.
- Adaptive suspension mode switching (e.g. Comfort/Sport) and ride-height
  adjustment.
- Fail-safe / degraded-mode behavior on sensor loss (e.g. wheel-speed
  sensor failure, steering-angle sensor fault).

## Common preconditions

Vehicle speed (many chassis functions are gated below or above a speed
threshold), wheel-speed sensor validity, brake-pedal state, ignition/park
state (relevant to EPB auto-apply), steering-wheel angle sensor
calibration state.

## Priority / safety notes

Nearly all chassis-domain requirements should default to Critical/high
priority -- braking and steering are core vehicle-safety functions.
Expect (and don't shortcut) heavy fault-injection and degraded-mode test
scenarios; this domain, alongside ADAS, typically carries the highest
concentration of Critical-priority test cases in the pipeline.

## Terminology pitfalls during resolution

- **"ESC" vs "ESP" vs "DSC"** -- OEM-specific naming for the same
  stability-control concept (Electronic Stability Control / Electronic
  Stability Program / Dynamic Stability Control); use whatever term the
  client's own documents use, don't normalize across OEM naming.
- **"EPB" vs "Auto-Hold"** -- Auto-Hold is a related but functionally
  distinct comfort feature (holds the vehicle stationary at a stop using
  the service brake) from the Electronic Parking Brake proper; don't
  conflate the two even though both may share the same physical actuator.
- **Per-wheel vs per-axle vs vehicle-level signals** -- confirm whether a
  requirement needs a specific corner's signal or an aggregate/vehicle-
  level one before resolving; picking the wrong granularity is a common
  resolution error in this domain.
