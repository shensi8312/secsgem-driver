# secsgem-driver — Serial → SECS/GEM bridge toolkit and runnable demo

> Status: **early / v0 / actively developed.** Open-source resources for
> learning, prototyping, simulator work, and integration evaluation. This is
> **not** a production-certified product.

Bridge legacy or lab equipment that speaks RS-232, ASCII, raw TCP, PLC, or a
similar simple interface toward SECS/GEM concepts, with a local host↔equipment
demo you can run without real hardware.

## What it is

- A small, config-shaped bridge layer for mapping legacy tool data into SVID,
  alarm, event, and remote-command concepts.
- A local simulated equipment flow that demonstrates 5 starter GEM E30-style
  scenarios.
- A practical starting point for integration scoping and simulator work.

## What it is not

- Not a turnkey or production-certified universal gateway.
- Not GEM300-certified.
- Not a guarantee of GEM compliance or support for any specific equipment.
- Not a replacement for equipment-specific mapping, validation, and customer
  acceptance testing.

Production deployment requires the actual equipment interface, host/MES
expectations, validation plan, and acceptance criteria.

## Built on

The runnable demo uses the minimal SECS-II / HSMS learning code included in this
repo so it can run locally without external equipment or a production SDK. It is
not a complete commercial SECS/GEM stack. Production integration can build on an
established open-source SECS/GEM package, a commercial SDK, or a customer-chosen
host path after equipment-specific validation.

The value here is the bridge, mapping, simulator, and scoping examples.

License: Apache-2.0.

## Quickstart

Install locally for development:

```bash
python -m pip install -e ".[dev]"
```

Run the full local demo:

```bash
python demo/run.py
```

Or run the same demo through Docker:

```bash
docker compose up
```

You will see:

1. communication establishment (`S1F14`)
2. status-variable read (`S1F4`)
3. alarm report (`S5F1`)
4. remote-command reply (`S2F42`)
5. event report (`S6F11`)

The recorded expected output is in:

```text
demo/expected_output.txt
```

## Tests

```bash
pytest
```

The tests verify that the demo output stays stable and that the SECS-II-style
bodies decode to the expected starter scenario structures.

## Repository map

```text
gateway/
  serial_adapter.py       # legacy ASCII command/status adapter
  gem_mapping.py          # SVID / alarm / event / remote-command mapping
demo/
  run.py                  # one-command local demo
  expected_output.txt     # recorded pass output
scenarios/
  README.md               # 5 starter scenario descriptions
configs/
  generic_legacy_serial_gateway.yaml
tests/
  test_gateway_scenarios.py
  test_legacy_gateway_demo.py
```

## Minimal gateway concept

```text
legacy equipment
  RS-232 / ASCII / TCP / PLC
        |
        v
adapter
  parse raw status line
  build simple command line
        |
        v
mapping layer
  SVID / ECID / alarm / event / remote command
        |
        v
SECS/GEM host path
  HSMS / SECS-II concepts
  equipment-specific validation required
```

## Example

```python
from gateway import DemoGateway

gateway = DemoGateway()
for result in gateway.run_starter_scenarios("TEMP=42.5;PRESSURE=1.2;STATE=IDLE;COUNT=17"):
    print(result.stream_function, result.summary)
```

## When to request integration help

Request a scoped integration review if you can describe:

- current equipment interface: RS-232, Modbus, ASCII, raw TCP, PLC, or other
- host/MES expectations: SVIDs, ECIDs, alarms, event reports, remote commands,
  and state model
- whether the target is learning, simulator work, pilot integration, or
  production acceptance
- customer acceptance criteria or conformance-test expectations

You should not send proprietary firmware, source code, or confidential
schematics for an initial scope review.

## MST resources

- [SECS/GEM resources](https://mst-sg.com/secs-gem-resources/)
- [SECS/GEM protocol guide](https://mst-sg.com/the-complete-guide-to-secs-gem-protocol-for-semiconductor-equipment/)
- [MST Singapore](https://mst-sg.com)

## Honesty note

This repo intentionally avoids download counts, customer counts, production
claims, and universal support claims. If a capability is planned, label it as
planned until it is implemented and tested.

## License

Apache License 2.0. See [LICENSE](LICENSE).
