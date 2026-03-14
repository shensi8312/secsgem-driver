"""Tests for SECS-II codec (SEMI E5)."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from secsgem.secs2 import encode, decode, FormatCode, Secs2Item


class TestEncodeDecode:
    """Round-trip encode/decode tests for all SECS-II data types."""

    def test_integer_u1(self):
        value = 42
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_integer_u2(self):
        value = 1000
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_integer_negative(self):
        value = -100
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_float(self):
        value = 3.14
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert abs(decoded - value) < 0.01

    def test_string(self):
        value = "AMAT Centura"
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_empty_string(self):
        value = ""
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_boolean_true(self):
        value = True
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded is True

    def test_boolean_false(self):
        value = False
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded is False

    def test_binary(self):
        value = b"\x01\x02\x03\x04"
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_list_simple(self):
        value = [1, 2, 3]
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_list_mixed(self):
        value = [42, "hello", 3.14, True]
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded[0] == 42
        assert decoded[1] == "hello"
        assert abs(decoded[2] - 3.14) < 0.01
        assert decoded[3] is True

    def test_list_nested(self):
        value = [[1, 2], [3, 4]]
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_empty_list(self):
        value = []
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_explicit_format_u4(self):
        encoded = encode(42, FormatCode.U4)
        decoded, consumed = decode(encoded)
        assert decoded == 42

    def test_explicit_format_f8(self):
        encoded = encode(3.14159, FormatCode.F8)
        decoded, consumed = decode(encoded)
        assert abs(decoded - 3.14159) < 1e-10

    def test_large_integer(self):
        value = 1000000
        encoded = encode(value)
        decoded, consumed = decode(encoded)
        assert decoded == value

    def test_zero(self):
        encoded = encode(0)
        decoded, consumed = decode(encoded)
        assert decoded == 0


class TestSecs2Item:
    """Tests for Secs2Item type inference."""

    def test_infer_list(self):
        item = Secs2Item([1, 2])
        assert item.format_code == FormatCode.LIST

    def test_infer_string(self):
        item = Secs2Item("hello")
        assert item.format_code == FormatCode.ASCII

    def test_infer_bool(self):
        item = Secs2Item(True)
        assert item.format_code == FormatCode.BOOLEAN

    def test_infer_float(self):
        item = Secs2Item(3.14)
        assert item.format_code == FormatCode.F4

    def test_infer_small_int(self):
        item = Secs2Item(42)
        assert item.format_code == FormatCode.U1

    def test_infer_negative_int(self):
        item = Secs2Item(-10)
        assert item.format_code == FormatCode.I1

    def test_explicit_override(self):
        item = Secs2Item(42, FormatCode.U4)
        assert item.format_code == FormatCode.U4


class TestEdgeCases:
    """Edge case and error handling tests."""

    def test_decode_empty_raises(self):
        with pytest.raises(ValueError):
            decode(b"")

    def test_non_ascii_raises(self):
        with pytest.raises(ValueError):
            encode("\u4e2d\u6587")  # Chinese characters

    def test_unsupported_type_raises(self):
        with pytest.raises(ValueError):
            Secs2Item(object())

    def test_consumed_bytes_correct(self):
        encoded = encode(42)
        _, consumed = decode(encoded)
        assert consumed == len(encoded)

    def test_message_key_value(self):
        """Test alternating key-value list pattern used in SECS messages."""
        value = ["MDLN", "AMAT", "SOFTREV", "1.0"]
        encoded = encode(value)
        decoded, _ = decode(encoded)
        assert decoded == value


class TestHSMSHeader:
    """Tests for HSMS header encode/decode."""

    def test_header_roundtrip(self):
        from secsgem.hsms import HSMSHeader, HSMSMessageType

        header = HSMSHeader(
            session_id=1,
            stream=1,
            function=1,
            p_type=0,
            s_type=HSMSMessageType.DATA_MESSAGE,
            system_bytes=12345,
        )
        data = header.to_bytes()
        assert len(data) == 10

        restored = HSMSHeader.from_bytes(data)
        assert restored.session_id == 1
        assert restored.stream == 1
        assert restored.function == 1
        assert restored.system_bytes == 12345

    def test_w_bit(self):
        from secsgem.hsms import HSMSHeader, HSMSMessageType

        header = HSMSHeader(
            session_id=0, stream=1, function=1,
            p_type=0, s_type=HSMSMessageType.DATA_MESSAGE,
            system_bytes=0,
        )
        assert not header.w_bit

        header.w_bit = True
        assert header.w_bit
        assert header.stream & 0x80 != 0

    def test_header_too_short_raises(self):
        from secsgem.hsms import HSMSHeader

        with pytest.raises(ValueError):
            HSMSHeader.from_bytes(b"\x00\x01\x02")
