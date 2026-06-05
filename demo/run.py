"""Run the local legacy equipment -> SECS/GEM starter demo."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gateway import DemoGateway, LegacyAsciiAdapter  # noqa: E402
from gateway.serial_adapter import LegacyCommand  # noqa: E402


LEGACY_LINE = "TEMP=42.5;PRESSURE=1.2;STATE=IDLE;COUNT=17"


def build_output() -> str:
    gateway = DemoGateway()
    adapter = LegacyAsciiAdapter()
    command_line = adapter.build_command_line(LegacyCommand("START", {"recipe": "DEMO"}))
    scenarios = gateway.run_starter_scenarios(LEGACY_LINE)

    lines = [
        "secsgem-driver local demo",
        "Status: early / v0 / integration-evaluation only",
        "This demo uses generic simulated equipment. No production compliance is claimed.",
        "",
        f"legacy equipment -> gateway: {LEGACY_LINE}",
        f"host remote command -> legacy equipment: {command_line}",
        "",
    ]

    labels = [
        "host establishes communication",
        "host reads status variables",
        "equipment raises an alarm",
        "host sends a remote command",
        "equipment sends an event report",
    ]

    for idx, (label, result) in enumerate(zip(labels, scenarios), start=1):
        lines.extend(
            [
                f"[{idx}/5] {label}",
                f"  reply: {result.stream_function} {result.summary}",
                f"  encoded: {result.encoded_hex}",
            ]
        )

    lines.extend(
        [
            "",
            "Done: 5 starter GEM E30-style scenarios completed locally.",
            "Next step for production: equipment-specific mapping, validation, and customer acceptance testing.",
        ]
    )

    return "\n".join(lines) + "\n"


def main() -> None:
    print(build_output(), end="")


if __name__ == "__main__":
    main()
