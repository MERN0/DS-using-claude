---
name: domain-knowledge
description: Domain-specific knowledge for the Powertrain automotive domain (engine, transmission & driveline) -- typical ECUs/modules, signal/command naming conventions, vehicle networks, common requirement and test-scenario patterns, preconditions, priority/safety notes, and terminology pitfalls. This domain is fixed for the whole run; use during discovery, extraction, resolution, merge planning, and drafting whenever requirement text, a sheet name, or a signal/command name uses powertrain-specific terminology that isn't immediately clear.
---

# Domain Knowledge: Powertrain (engine, transmission & driveline)

Engine/transmission management for ICE and hybrid drivetrains -- distinct
from the EV domain's pure-electric traction/battery scope, though a hybrid
platform may reference both. Use this to recognize domain terminology
faster; it never substitutes for actually finding a signal/command in a
supporting document during resolution.

## Scope

Engine management, transmission control (automatic/DCT/AMT/manual-assist),
clutch/torque converter, driveline (differential, AWD transfer case),
emissions/exhaust aftertreatment, engine idle-stop, cooling system, and
(on hybrids) power-split/mode-transition logic shared with an HCU.

## Typical ECUs / modules

- **ECM / PCM (Engine / Powertrain Control Module)** -- engine management;
  naming varies by OEM, treat as referring to the same class of module
  unless the source explicitly distinguishes them.
- **TCU (Transmission Control Unit)** -- shift logic and clutch/torque
  converter control.
- **HCU (Hybrid Control Unit)** -- present only on hybrid variants;
  coordinates engine/motor torque split.
- **Aftertreatment Control Module** -- SCR/DPF regeneration and emissions
  control, sometimes folded into the ECM.
- **Cooling Fan Controller** -- radiator fan speed/staging.

## Common signal & command categories

Expect names like: `EngineRPMValue`, `ThrottlePositionCmd` /
`ThrottlePositionStatus`, `GearSelectCmd` / `GearStatus`,
`ClutchEngageCmd` / `ClutchStatus`, `EngineTorqueRequest` /
`EngineTorqueStatus`, `CoolantTempValue`, `OilPressureValue`,
`IdleStopEnableCmd` / `IdleStopStatus`, `ExhaustTempValue`,
`DPFRegenCmd` / `DPFStatus`, `AWDEngageCmd` / `AWDStatus`,
`CruiseControlSetSpeedCmd`, `MILCmd` (Malfunction Indicator Lamp /
"check engine" lamp).

## Vehicle networks

High-speed CAN, typically on a dedicated powertrain CAN segment that a
gateway separates from the body/comfort CAN; OBD-II/UDS diagnostics ride
over CAN as well and may be a separate supporting-document sheet from the
normal signal list; some higher-end platforms use FlexRay for
hard-real-time transmission control.

## Typical requirement & test-scenario themes

- Gear-shift logic / shift schedule under varying load and throttle input.
- Idle-stop (start/stop) triggering and restart conditions.
- Torque-request arbitration between driver input and limiters (traction
  control, cruise control, transmission protection).
- Aftertreatment regeneration triggering and completion (DPF/SCR).
- Cooling-fan activation thresholds tied to coolant temperature.
- Diagnostic Trouble Code (DTC) setting and MIL illumination on fault.
- Hybrid-only: EV-only vs engine-assist mode transition logic.

## Common preconditions

Engine running/cranking state, transmission selector position
(Park/Neutral/Drive/Reverse), coolant temperature threshold, vehicle
speed, brake pedal state (relevant to idle-stop restart), and on hybrids,
battery SOC (affects mode selection) -- shared vocabulary with the EV
domain but resolved against this run's own supporting documents, not
assumed.

## Priority / safety notes

Torque-arbitration and gear-shift-lockout requirements are frequently
Critical/high-priority (unintended-acceleration prevention, preventing an
unsafe shift). Emissions-related requirements are often
regulatory-critical even when not directly a safety hazard -- don't
downgrade priority on these without explicit source justification.

## Terminology pitfalls during resolution

- **"PCM" vs "ECM" vs "ECU"** -- OEM-specific naming for what may be the
  same physical module; use whichever term the client's own documents use,
  don't normalize across OEM naming conventions.
- **Gear naming must match the source exactly** -- P/R/N/D letter naming
  vs numeric gear-position naming (1st/2nd/... or G1/G2/...) are not
  interchangeable; use the alias the sheet actually gives.
- **"Torque Request" is layered** -- driver-requested torque, arbitrated
  torque, and actual delivered torque are often distinct signals; confirm
  which layer a requirement is actually testing before resolving.
