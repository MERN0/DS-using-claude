---
name: domain-knowledge
description: Domain-specific knowledge for the Telematics automotive domain (connectivity, TCU, remote services, eCall, OTA) -- typical ECUs/modules, signal/command naming conventions, vehicle networks, common requirement and test-scenario patterns, preconditions, priority/safety notes, and terminology pitfalls. This domain is fixed for the whole run; use during discovery, extraction, resolution, merge planning, and drafting whenever requirement text, a sheet name, or a signal/command name uses telematics-specific terminology that isn't immediately clear.
---

# Domain Knowledge: Telematics (connectivity, TCU, remote services, eCall, OTA)

Cellular/GNSS connectivity and everything that depends on it: remote
services, emergency calling, and over-the-air updates. Use this to
recognize domain terminology faster; it never substitutes for actually
finding a signal/command in a supporting document during resolution.

## Scope

Telematics Control Unit (TCU), cellular connectivity, GNSS/GPS
positioning, eCall/bCall (emergency/breakdown call), remote vehicle
services (remote lock/unlock, remote start, remote climate), vehicle
tracking/geofencing, over-the-air (OTA) software updates, fleet telemetry
reporting, SIM/eSIM management.

## Typical ECUs / modules

- **TCU (Telematics Control Unit)** -- central connectivity module;
  caution: "TCU" is also used elsewhere in the vehicle for "Transmission
  Control Unit" (see pitfalls below).
- **GNSS receiver module** -- often integrated into the TCU rather than
  standalone.
- **Cellular modem** -- also frequently integrated into the TCU.
- **eCall control unit** -- may be a discrete module or folded into the
  TCU; takes crash-severity input from the airbag/restraint system.
- **OTA update manager / gateway ECU** -- coordinates update download,
  verification, and staged rollout to other ECUs.
- **Remote service gateway** -- backend/cloud-facing endpoint for
  app-initiated remote commands.

## Common signal & command categories

Expect names like: `GNSSPositionValue` (lat/long), `GNSSFixStatus`,
`CellularSignalStrengthValue`, `CellularConnectionStatus`,
`eCallTriggerCmd` (manual/automatic) / `eCallStatus`, `RemoteLockCmd` /
`RemoteLockStatus` (distinct from local RKE-triggered locking in the BCM
domain), `RemoteStartCmd` / `RemoteStartStatus`, `RemoteClimateCmd`,
`GeofenceEnterExitStatus`, `OTAUpdateAvailableStatus` /
`OTAUpdateProgressCmd` / `OTAUpdateStatus`, `SIMStatusValue`,
`CrashSeverityValue` (input to eCall auto-trigger).

## Vehicle networks

Vehicle CAN/Ethernet for internal signal exchange with other ECUs;
cellular network (2G/3G/4G/5G, per platform generation) plus backend
cloud APIs for remote services -- often mocked/simulated on the bench, so
check whether the supporting documents model this as a real network
signal or a simulated/injected one; GNSS satellite signal for
positioning; Bluetooth for some phone-as-key remote features;
increasingly DoIP/Ethernet for OTA payload delivery.

## Typical requirement & test-scenario themes

- Automatic eCall triggering on a crash-severity threshold, with a
  manual-override/cancel window.
- Remote command authentication/authorization -- a remote command must
  originate from a paired app/backend, not be accepted unauthenticated.
- OTA update download/verify/apply/rollback sequencing, including
  failure-recovery behavior.
- Connectivity loss and reconnection handling (cellular drop, GNSS signal
  loss).
- Geofence entry/exit notification.
- Position accuracy / time-to-first-fix requirements.
- SIM provisioning / roaming behavior.

## Common preconditions

Cellular network availability/signal strength, GNSS fix acquired, vehicle
power state (many remote services require sufficient 12V battery charge
or a specific power mode), backend/cloud service reachability (often
simulated for bench testing rather than a live network dependency), and
for most remote convenience features, ignition-off state.

## Priority / safety notes

eCall/crash-related requirements are typically Critical and often
regulatory-driven (e.g. mandated emergency-call requirements in some
markets) -- default to Critical unless the source states otherwise. OTA
update failure-handling (safe rollback, preventing a failed update from
leaving an ECU unusable) is high priority given the consequence of
getting it wrong. Remote command security/authentication requirements are
both safety- and security-relevant.

## Terminology pitfalls during resolution

- **"TCU" is overloaded** -- Telematics Control Unit here, but
  "Transmission Control Unit" in the powertrain domain; if a requirements
  sheet mixes domains or the supporting document set is ambiguous, confirm
  which TCU a signal belongs to before resolving.
- **eCall vs bCall vs SOS-call** -- automatic emergency call, breakdown
  call, and manually-triggered SOS call are related but distinct features
  with their own trigger conditions and often their own status signals;
  don't assume one requirement's resolution covers all three.
- **"Remote" vs "local" commands** -- a remote-triggered action (e.g.
  `RemoteLockCmd` from the telematics/backend path) is typically a
  distinct signal from the equivalent locally-triggered command (e.g. RKE
  in the BCM domain) even when they ultimately actuate the same lock;
  resolve against the telematics-specific alias, not the local one.
