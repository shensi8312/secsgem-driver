"""Config-shaped SECS/GEM starter mapping used by the runnable demo.

The bodies are SECS-II-style examples for learning and integration scoping. They
are deliberately small and do not replace equipment-specific GEM validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from secsgem import encode, format_bytes


@dataclass(frozen=True)
class StatusSnapshot:
    temperature_c: float
    pressure_torr: float
    state: str
    lot_count: int


@dataclass(frozen=True)
class DemoScenarioResult:
    name: str
    stream_function: str
    body: Any
    encoded: bytes
    summary: str

    @property
    def encoded_hex(self) -> str:
        return format_bytes(self.encoded).replace("\n", " ")


class DemoGateway:
    """Map one generic legacy tool into 5 starter GEM E30-style scenarios."""

    MDLN = "MST-DEMO-GATEWAY"
    SOFTREV = "0.1.0"

    CEID_STATUS_UPDATE = 2001
    RPTID_STATUS = 3001

    SVID_TEMPERATURE = 1001
    SVID_PRESSURE = 1002
    SVID_STATE = 1003
    SVID_LOT_COUNT = 1004

    ALID_DOOR_OPEN = 5001

    def snapshot_from_fields(self, fields: dict[str, str]) -> StatusSnapshot:
        missing = {"TEMP", "PRESSURE", "STATE", "COUNT"} - fields.keys()
        if missing:
            raise ValueError(f"missing legacy fields: {', '.join(sorted(missing))}")

        return StatusSnapshot(
            temperature_c=float(fields["TEMP"]),
            pressure_torr=float(fields["PRESSURE"]),
            state=fields["STATE"].upper(),
            lot_count=int(fields["COUNT"]),
        )

    def establish_communication(self) -> DemoScenarioResult:
        body = [0, self.MDLN, self.SOFTREV]
        return DemoScenarioResult(
            name="communication establishment",
            stream_function="S1F14",
            body=body,
            encoded=encode(body),
            summary=f"COMMACK=0 MDLN={self.MDLN} SOFTREV={self.SOFTREV}",
        )

    def read_svids(self, snapshot: StatusSnapshot) -> DemoScenarioResult:
        values = [
            [self.SVID_TEMPERATURE, snapshot.temperature_c],
            [self.SVID_PRESSURE, snapshot.pressure_torr],
            [self.SVID_STATE, snapshot.state],
            [self.SVID_LOT_COUNT, snapshot.lot_count],
        ]
        return DemoScenarioResult(
            name="status variable read",
            stream_function="S1F4",
            body=values,
            encoded=encode(values),
            summary=(
                f"TEMP={snapshot.temperature_c}C PRESSURE={snapshot.pressure_torr}Torr "
                f"STATE={snapshot.state} COUNT={snapshot.lot_count}"
            ),
        )

    def alarm_report(self) -> DemoScenarioResult:
        body = [1, self.ALID_DOOR_OPEN, "Demo door interlock alarm"]
        return DemoScenarioResult(
            name="alarm report",
            stream_function="S5F1",
            body=body,
            encoded=encode(body),
            summary=f"ALCD=1 ALID={self.ALID_DOOR_OPEN} ALTX=Demo door interlock alarm",
        )

    def remote_command_reply(self, command: str = "START") -> DemoScenarioResult:
        body = [command.upper(), 0, []]
        return DemoScenarioResult(
            name="remote command reply",
            stream_function="S2F42",
            body=body,
            encoded=encode(body),
            summary=f"RCMD={command.upper()} HCACK=0",
        )

    def event_report(self, snapshot: StatusSnapshot) -> DemoScenarioResult:
        body = [
            1,
            self.CEID_STATUS_UPDATE,
            [
                [
                    self.RPTID_STATUS,
                    [
                        [self.SVID_TEMPERATURE, snapshot.temperature_c],
                        [self.SVID_PRESSURE, snapshot.pressure_torr],
                        [self.SVID_STATE, snapshot.state],
                        [self.SVID_LOT_COUNT, snapshot.lot_count],
                    ],
                ]
            ],
        ]
        return DemoScenarioResult(
            name="event report",
            stream_function="S6F11",
            body=body,
            encoded=encode(body),
            summary=f"CEID={self.CEID_STATUS_UPDATE} RPTID={self.RPTID_STATUS}",
        )

    def run_starter_scenarios(self, legacy_line: str) -> list[DemoScenarioResult]:
        from .serial_adapter import LegacyAsciiAdapter

        adapter = LegacyAsciiAdapter()
        snapshot = self.snapshot_from_fields(adapter.parse_status_line(legacy_line))
        return [
            self.establish_communication(),
            self.read_svids(snapshot),
            self.alarm_report(),
            self.remote_command_reply("START"),
            self.event_report(snapshot),
        ]
