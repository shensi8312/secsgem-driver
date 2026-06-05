"""Minimal legacy serial/ASCII -> SECS/GEM-style mapping demo.

This demo is intentionally local-only. It does not connect to real equipment or
claim production compliance. It shows the mapping work needed before a real
gateway can be validated against a customer's host/MES.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from secsgem import encode, format_bytes  # noqa: E402


@dataclass(frozen=True)
class LegacySnapshot:
    temperature_c: float
    pressure_torr: float
    state: str


@dataclass(frozen=True)
class GatewayEvent:
    ceid: int
    svid_values: Dict[int, object]
    encoded_s6f11: bytes


class LegacyGateway:
    """Map a simple legacy ASCII status line to a SECS/GEM-style event body."""

    CEID_STATUS_UPDATE = 2001
    REPORT_ID_STATUS = 3001
    SVID_TEMPERATURE = 1001
    SVID_PRESSURE = 1002
    SVID_STATE = 1003

    def parse_legacy_line(self, line: str) -> LegacySnapshot:
        fields = {}
        for part in line.strip().split(";"):
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"invalid legacy field: {part!r}")
            key, value = part.split("=", 1)
            fields[key.strip().upper()] = value.strip()

        missing = {"TEMP", "PRESSURE", "STATE"} - fields.keys()
        if missing:
            raise ValueError(f"missing legacy fields: {', '.join(sorted(missing))}")

        return LegacySnapshot(
            temperature_c=float(fields["TEMP"]),
            pressure_torr=float(fields["PRESSURE"]),
            state=fields["STATE"].upper(),
        )

    def build_event(self, snapshot: LegacySnapshot) -> GatewayEvent:
        svid_values: Dict[int, object] = {
            self.SVID_TEMPERATURE: snapshot.temperature_c,
            self.SVID_PRESSURE: snapshot.pressure_torr,
            self.SVID_STATE: snapshot.state,
        }

        # Simplified S6F11-style body:
        # [DATAID, CEID, [[RPTID, [[SVID, VALUE], ...]]]]
        body = [
            1,
            self.CEID_STATUS_UPDATE,
            [
                [
                    self.REPORT_ID_STATUS,
                    [
                        [self.SVID_TEMPERATURE, snapshot.temperature_c],
                        [self.SVID_PRESSURE, snapshot.pressure_torr],
                        [self.SVID_STATE, snapshot.state],
                    ],
                ]
            ],
        ]
        return GatewayEvent(
            ceid=self.CEID_STATUS_UPDATE,
            svid_values=svid_values,
            encoded_s6f11=encode(body),
        )


def main() -> None:
    line = "TEMP=42.5;PRESSURE=1.2;STATE=IDLE"
    gateway = LegacyGateway()
    snapshot = gateway.parse_legacy_line(line)
    event = gateway.build_event(snapshot)

    print(f"Legacy line: {line}")
    print(f"Mapped SVIDs: {event.svid_values}")
    print(f"Event CEID: {event.ceid}")
    print("Encoded S6F11 bytes:")
    print(format_bytes(event.encoded_s6f11))


if __name__ == "__main__":
    main()
