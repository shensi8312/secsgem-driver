from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from demo.run import LEGACY_LINE, build_output  # noqa: E402
from gateway import DemoGateway, LegacyAsciiAdapter  # noqa: E402
from gateway.serial_adapter import LegacyCommand  # noqa: E402
import pytest  # noqa: E402
from secsgem import decode  # noqa: E402


def test_demo_output_matches_recorded_expected_output():
    expected = (ROOT / "demo" / "expected_output.txt").read_text(encoding="utf-8")
    assert build_output() == expected


def test_starter_scenarios_decode_to_expected_bodies():
    gateway = DemoGateway()
    results = gateway.run_starter_scenarios(LEGACY_LINE)

    assert [result.stream_function for result in results] == [
        "S1F14",
        "S1F4",
        "S5F1",
        "S2F42",
        "S6F11",
    ]

    decoded = []
    for result in results:
        body, consumed = decode(result.encoded)
        assert consumed == len(result.encoded)
        decoded.append(body)

    assert decoded[0] == [0, "MST-DEMO-GATEWAY", "0.1.0"]
    assert decoded[1][0] == [1001, pytest.approx(42.5)]
    assert decoded[1][1] == [1002, pytest.approx(1.2)]
    assert decoded[1][2] == [1003, "IDLE"]
    assert decoded[1][3] == [1004, 17]
    assert decoded[2] == [1, 5001, "Demo door interlock alarm"]
    assert decoded[3] == ["START", 0, []]
    assert decoded[4][1] == 2001
    assert decoded[4][2][0][0] == 3001


def test_legacy_ascii_adapter_builds_remote_command_line():
    adapter = LegacyAsciiAdapter()
    command = LegacyCommand("START", {"recipe": "DEMO"})

    assert adapter.build_command_line(command) == "CMD=START;RECIPE=DEMO"
