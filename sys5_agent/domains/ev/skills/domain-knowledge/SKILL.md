---
name: domain-knowledge
description: Domain-specific knowledge for the Electric Vehicle (EV) automotive domain -- battery/BMS, charging, and traction motor control -- typical ECUs/modules, signal/command naming conventions, vehicle networks, common requirement and test-scenario patterns, preconditions, priority/safety notes, and terminology pitfalls. This domain is fixed for the whole run; use during discovery, extraction, resolution, merge planning, and drafting whenever requirement text, a sheet name, or a signal/command name uses EV-specific terminology that isn't immediately clear.
---

# Domain Knowledge: EV (Electric Vehicle powertrain, battery & charging)

High-voltage battery, charging, and traction motor control. Use this to
recognize domain terminology faster; it never substitutes for actually
finding a signal/command in a supporting document during resolution.

## Scope

High-voltage (HV) battery pack and BMS, on-board AC charger (OBC) and DC
fast-charging, traction inverter/motor control, HV contactor/interlock
management, battery thermal management, regenerative braking, range/SOC
reporting, charge port lock.

## Typical ECUs / modules

- **BMS (Battery Management System)** -- cell/pack monitoring, SOC/SOH
  estimation, contactor and thermal-management coordination.
- **VCU / EVCU (Vehicle/EV Control Unit)** -- top-level torque and energy
  arbitration.
- **MCU (Motor Control Unit) / Inverter** -- traction motor torque
  control.
- **OBC (On-Board Charger)** -- AC charging (Level 1/2), DC-DC conversion
  for the 12V system.
- **Charge Port Controller** -- port lock, pilot-signal detection, DC
  fast-charge communication.
- **Battery Thermal Management Controller** -- coolant pump/heater/chiller
  for pack temperature control.

## Common signal & command categories

Expect names like: `SOCValue` (State of Charge), `SOHValue` (State of
Health), `PackVoltage`, `PackCurrent`, `CellVoltageMax` / `CellVoltageMin`,
`BatteryTempMax` / `BatteryTempMin`, `ChargePortLockCmd` /
`ChargePortLockStatus`, `ChargeStartCmd` / `ChargeStatus`,
`ChargeCurrentLimit`, `DCFastChargeStatus`, `RegenBrakeLevelCmd`,
`MotorTorqueCmd` / `MotorTorqueStatus`, `ContactorCmd` / `ContactorStatus`
(main HV contactors), `IsolationResistanceStatus`, `RangeEstimateValue`.

## Vehicle networks

High-speed CAN/CAN-FD for HV powertrain and VCU coordination; a dedicated
cell-monitor daisy-chain link (e.g. isoSPI-style) between BMS and cell
sensors is often a separate sub-network not on the main vehicle bus;
charging communication follows a charging-standard handshake protocol
(e.g. ISO 15118 / DIN 70121 / CHAdeMO / CCS-style, transported over
power-line communication for AC/DC charging) -- if a requirement mentions
charger handshake or pilot signal, check whether a dedicated
charging-protocol reference exists among the supporting docs before
assuming it's on the plain vehicle CAN.

## Typical requirement & test-scenario themes

- SOC/SOH accuracy, display, and low-SOC warning thresholds.
- Charge start/stop/interrupt handling, including user-initiated abort.
- Charge current tapering as the pack approaches full SOC.
- Thermal derating -- charge/discharge power limited at temperature
  extremes.
- HV contactor open/close sequencing and interlock (safety-critical).
- Regenerative braking blend with friction brakes.
- Charge port lock/unlock and charge-cable pilot-signal detection.
- Fault handling: over-voltage/over-current/over-temperature shutdown,
  isolation-resistance fault.
- Range estimation logic under varying conditions.

## Common preconditions

HV system state (Ready/Not-Ready), charge cable connected and pilot signal
present, vehicle in Park (charging typically requires Park, not just
ignition-off), battery temperature within its operating window, 12V/aux
battery sufficiently charged to wake the HV system.

## Priority / safety notes

HV safety interlocks (contactor sequencing, isolation-fault detection,
thermal-runaway response) are almost always Critical/high-priority by
default -- expect fault-injection and degraded-mode scenarios, and don't
downgrade these without explicit source-document justification. Charging
faults (over-current, over-temperature during charge) are typically
Critical too.

## Terminology pitfalls during resolution

- **SOC vs SOH vs DOD** -- State of Charge, State of Health, and Depth of
  Discharge are three distinct values; don't substitute one for another.
- **Charging state machine has many sub-states** -- Precharge / Charging /
  Taper / Complete / Fault are typically separate status values, not one
  boolean "charging" flag.
- **HV vs LV (12V) context** -- a signal name mentioning "battery" without
  qualification could mean the HV traction pack or the 12V auxiliary
  battery; confirm which before resolving.
- **"Contactor" vs "Relay"** -- HV contactors are functionally relays but
  the documents usually use "contactor" specifically for the HV main
  disconnects; don't conflate with a generic 12V relay signal.
