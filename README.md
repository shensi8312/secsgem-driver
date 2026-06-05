# secsgem-driver

Early open-source Python resources for SECS/GEM learning, simulator work, and equipment-integration evaluation.

This repository is **not** a production-certified SECS/GEM or GEM300 solution. It is a v0 engineering project for teams that need to understand HSMS / SECS-II concepts, build small prototypes, and scope the gap between a legacy tool interface and a production host connection.

Production deployment requires equipment-specific mapping, validation, customer acceptance testing, and often a commercial SDK or a custom integration program.

## Current status

- Status: **early / v0**
- License: Apache-2.0
- Scope: protocol learning, simulator work, local demos, integration evaluation
- Not included: production certification, GEM300 compliance guarantee, universal equipment support, customer acceptance test coverage

## What is included

- A SECS-II codec for common data items used in examples.
- HSMS framing and connection primitives for engineering experiments.
- Configuration-driven message definitions for generic tools.
- A minimal local demo that maps simple legacy serial-style lines into SECS/GEM-style status variables, events, and alarms.

## What this is not

- Not a turnkey universal gateway.
- Not ready for production use without project-specific validation.
- Not GEM300-certified.
- Not a promise that any specific equipment model is supported.
- Not a substitute for equipment-specific host acceptance testing.

## Quick start

Install locally for development:

```bash
python -m pip install -e ".[dev]"
```

Run tests:

```bash
pytest
```

Run the minimal legacy gateway demo:

```bash
python examples/legacy_serial_gateway_demo.py
```

Expected output:

```text
Legacy line: TEMP=42.5;PRESSURE=1.2;STATE=IDLE
Mapped SVIDs: {1001: 42.5, 1002: 1.2, 1003: 'IDLE'}
Event CEID: 2001
Encoded S6F11 bytes: ...
```

The demo does not connect to real equipment. It shows the mapping layer that a real integration project would need to replace with an actual RS-232 / Modbus / ASCII / TCP adapter and a validated SECS/GEM host path.

## Minimal gateway concept

```text
legacy equipment
  RS-232 / ASCII / TCP / PLC
        |
        v
mapping layer
  parse raw line
  map values to SVID / ECID / alarms
  build SECS-II message body
        |
        v
SECS/GEM host path
  HSMS / SECS-II
  equipment-specific validation required
```

## Example mapping

```python
from examples.legacy_serial_gateway_demo import LegacyGateway

gateway = LegacyGateway()
snapshot = gateway.parse_legacy_line("TEMP=42.5;PRESSURE=1.2;STATE=IDLE")
event = gateway.build_event(snapshot)

print(event.svid_values)
print(event.encoded_s6f11.hex())
```

## Configuration

Use `configs/template.yaml` as a generic starting point. Use `configs/generic_legacy_serial_gateway.yaml` to describe a simple legacy adapter evaluation scenario.

The sample files use generic tool names only. They do not imply support for any specific vendor, customer, or equipment model.

## When to request integration help

Request a scoped integration review if you can describe:

- Current equipment interface: RS-232, Modbus, ASCII, raw TCP, PLC, or other.
- Host/MES expectation: SVIDs, ECIDs, alarms, reports, remote commands, state model.
- Whether the target is learning, simulator work, pilot integration, or production acceptance.
- Any customer acceptance criteria or conformance test expectations.

You should not send proprietary firmware, source code, or confidential schematics for an initial scope review.

## MST resources

- [SECS/GEM resources](https://mst-sg.com/secs-gem-resources/)
- [SECS/GEM protocol guide](https://mst-sg.com/the-complete-guide-to-secs-gem-protocol-for-semiconductor-equipment/)
- [SECS/GEM vs OPC UA comparison](https://mst-sg.com/secs-gem-vs-opc-ua-which-communication-protocol-is-right-for-your-smart-fab/)
- [MST Singapore](https://mst-sg.com)

## Package metadata

This project is intentionally versioned as `0.x` while it remains an evaluation resource. Do not treat it as production-stable without your own validation.

## License

Apache License 2.0. See [LICENSE](LICENSE).
