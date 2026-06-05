import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from examples.legacy_serial_gateway_demo import LegacyGateway  # noqa: E402
from secsgem import decode  # noqa: E402


def test_legacy_line_maps_to_svid_event():
    gateway = LegacyGateway()
    snapshot = gateway.parse_legacy_line("TEMP=42.5;PRESSURE=1.2;STATE=IDLE")
    event = gateway.build_event(snapshot)

    assert event.ceid == 2001
    assert event.svid_values == {1001: 42.5, 1002: 1.2, 1003: "IDLE"}

    decoded, consumed = decode(event.encoded_s6f11)
    assert consumed == len(event.encoded_s6f11)
    assert decoded[1] == 2001
    assert decoded[2][0][0] == 3001
    assert decoded[2][0][1][0] == [1001, pytest.approx(42.5)]
    assert decoded[2][0][1][1] == [1002, pytest.approx(1.2)]
    assert decoded[2][0][1][2] == [1003, "IDLE"]


def test_legacy_line_requires_expected_fields():
    gateway = LegacyGateway()

    with pytest.raises(ValueError, match="missing legacy fields"):
        gateway.parse_legacy_line("TEMP=42.5;STATE=IDLE")
