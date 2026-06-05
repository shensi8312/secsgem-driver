"""Simple legacy ASCII adapter used by the local demo."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LegacyCommand:
    name: str
    parameters: dict[str, str]


class LegacyAsciiAdapter:
    """Parse a tiny `KEY=VALUE;...` legacy equipment line.

    A real integration would replace this with an equipment-specific RS-232,
    Modbus, raw TCP, PLC, or vendor protocol adapter.
    """

    def parse_status_line(self, line: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for part in line.strip().split(";"):
            if not part:
                continue
            if "=" not in part:
                raise ValueError(f"invalid legacy field: {part!r}")
            key, value = part.split("=", 1)
            fields[key.strip().upper()] = value.strip()
        return fields

    def build_command_line(self, command: LegacyCommand) -> str:
        params = ";".join(f"{key.upper()}={value}" for key, value in command.parameters.items())
        return f"CMD={command.name.upper()}" + (f";{params}" if params else "")
