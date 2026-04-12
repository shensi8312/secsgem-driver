# secsgem-driver

A production-ready, configuration-driven **SECS/GEM driver** for semiconductor equipment communication in Python.

Built on the SEMI standards (E4, E5, E30, E37), this library provides a clean async API for connecting to semiconductor manufacturing equipment via HSMS/SECS-II protocols.

## Features

- **HSMS Protocol** (SEMI E37) - Full implementation with active/passive modes, Select/Deselect/Linktest, heartbeat
- **SECS-II Codec** (SEMI E5) - Complete encode/decode for all data types (List, ASCII, Binary, Boolean, integers, floats)
- **Configuration-Driven** - YAML-based equipment profiles, no hardcoded message definitions
- **Async/Await** - Built on Python asyncio for non-blocking I/O
- **Auto-Reconnect** - Configurable reconnection with backoff
- **Event System** - Subscribe to equipment events (S6F11) and alarms (S5F1) with decorators
- **Type-Safe** - Pydantic-validated configuration, typed APIs
- **Zero Dependencies on AI/ML** - Pure protocol implementation, lightweight enough for any environment

## Quick Start

### Install

```bash
pip install secsgem-driver
```

### Connect to Equipment

```python
import asyncio
from secsgem import SecsGemDriver

async def main():
    driver = SecsGemDriver("configs/amat_centura.yaml")

    await driver.connect()

    # Send S1F1 (Are You There)
    response = await driver.send("S1F1")
    print(f"Equipment: {response}")

    # Send remote command
    await driver.send_command("START", {
        "RECIPE_ID": "ALU_001",
        "LOT_ID": "LOT-2025-001",
    })

    # Subscribe to events
    @driver.on_event(100)  # PROCESS_START
    async def on_process_start(event_data):
        print(f"Process started: {event_data}")

    await driver.disconnect()

asyncio.run(main())
```

### Low-Level HSMS Access

```python
from secsgem import HSMSConnection

connection = HSMSConnection(
    host="192.168.10.101",
    port=5000,
    mode="active",
)

await connection.connect()
reply = await connection.send_data_message(
    stream=1, function=1, wait_bit=True
)
await connection.disconnect()
```

### SECS-II Encoding/Decoding

```python
from secsgem import encode, decode, format_bytes

# Encode Python objects to SECS-II binary
encoded = encode([1, "RECIPE_A", 3.14, True])

# Decode SECS-II binary back to Python
decoded, _ = decode(encoded)

# Pretty-print hex dump
print(format_bytes(encoded))
```

## Equipment Configuration

Define your equipment in YAML - no code changes needed for new equipment types:

```yaml
equipment:
  id: "CENTURA_001"
  type: "AMAT_CENTURA"
  vendor: "Applied Materials"

connection:
  mode: "active"
  ip_address: "192.168.10.101"
  port: 5000

messages:
  S1F1:
    stream: 1
    function: 1
    wait_bit: true
    description: "Are You There Request"

commands:
  START:
    description: "Start process"
    parameters:
      - name: "RECIPE_ID"
        type: "ASCII"
        required: true
```

See [`configs/`](configs/) for complete examples covering AMAT Centura, Lam Kiyo, TEL Lithius, and a generic template.

## Architecture

```
secsgem-driver
├── hsms.py       # HSMS protocol (TCP, Select/Deselect, Linktest)
├── secs2.py      # SECS-II codec (encode/decode all format codes)
├── config.py     # YAML config loader with Pydantic validation
├── messages.py   # Dynamic message builder from config definitions
└── driver.py     # High-level SecsGemDriver API
```

The library is designed as a standalone protocol layer. It can be used directly for equipment communication, or as a foundation for higher-level systems like:

- MES (Manufacturing Execution System) integration
- Equipment data collection and monitoring
- Run-to-Run (R2R) process control
- Virtual Metrology (VM) systems
- Fault Detection & Classification (FDC)

## Supported SEMI Standards

| Standard | Description | Status |
|----------|-------------|--------|
| SEMI E4  | SECS-I Transport | Message format support |
| SEMI E5  | SECS-II Message Content | Full codec |
| SEMI E30 | GEM Behavior | Core scenarios |
| SEMI E37 | HSMS Transport | Full implementation |

## Requirements

- Python 3.9+
- PyYAML
- Pydantic v2

## About

Developed and maintained by [Moore Solution Technology (MST)](https://mst-sg.com) — AI infrastructure for semiconductor manufacturing.

This driver powers the communication layer of the [NeuroBox E series](https://mst-sg.com/news/neurobox-e3200-production-ai/) edge AI platform for semiconductor fabs and equipment manufacturers.

### MST Product Ecosystem

| Product | Description | Learn More |
|---------|-------------|------------|
| **NeuroBox D** | AI design automation — P&ID to native SolidWorks 3D assembly | [Product Page](https://mst-sg.com/neurobox-d/) |
| **NeuroBox E5200** | Smart DOE for equipment commissioning — 80% fewer test wafers | [How Smart DOE Works](https://mst-sg.com/stop-burning-test-wafers-how-smart-doe-cuts-equipment-commissioning-costs-by-80/) |
| **NeuroBox E3200** | Production-line AI — Virtual Metrology, R2R, FDC at sub-50ms | [VM Explained](https://mst-sg.com/virtual-metrology-explained-how-ai-predicts-wafer-quality-without-physical-measurement/) |
| **NeuroEnergy** | AI energy management for semiconductor fabs | [Learn More](https://mst-sg.com/news/neuroenergy-launch/) |

### Related Resources

- [The Complete Guide to SECS/GEM Protocol](https://mst-sg.com/the-complete-guide-to-secs-gem-protocol-for-semiconductor-equipment/)
- [SECS/GEM vs OPC UA Comparison](https://mst-sg.com/secs-gem-vs-opc-ua-which-communication-protocol-is-right-for-your-smart-fab/)
- [GEM300 Standard Guide](https://mst-sg.com/gem300-standard-300mm-semiconductor-equipment-guide/)
- [Run-to-Run Control with AI](https://mst-sg.com/run-to-run-control-the-ai-system-that-automatically-tunes-every-wafer/)
- [FDC: AI Reduces False Alarms by 70%](https://mst-sg.com/fdc-fault-detection-and-classification-how-ai-reduces-false-alarms-by-70/)

**Websites**: [mst-sg.com](https://mst-sg.com) (Global) | [ai-mst.com](https://ai-mst.com) (中国站)

## License

Apache License 2.0 - see [LICENSE](LICENSE) for details.
