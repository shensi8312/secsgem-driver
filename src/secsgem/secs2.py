"""
SECS-II Codec - Encoding and Decoding
======================================

This module implements SECS-II (SEMI E5) message encoding and decoding.
It converts between Python objects and SECS-II binary format.

SECS-II Format Structure:
    [Format Byte][Length Bytes][Data Bytes]

Format Byte:
    - Bits 7-2: Format Code (data type)
    - Bits 1-0: Number of length bytes (0-3)

Supported Data Types:
    - List (L): Container for other items
    - Binary (B): Raw binary data
    - Boolean: True/False values
    - ASCII (A): ASCII text strings
    - I1, I2, I4, I8: Signed integers (1, 2, 4, 8 bytes)
    - F4, F8: Floating point (4, 8 bytes)
    - U1, U2, U4, U8: Unsigned integers (1, 2, 4, 8 bytes)

Reference: SEMI E5 - SECS-II Message Content
"""

import struct
from typing import Any, List, Union, Tuple
from enum import IntEnum


# ============================================================================
# SECS-II Format Codes
# ============================================================================

class FormatCode(IntEnum):
    """SECS-II Format Codes (6-bit values)"""
    LIST = 0b000000      # 0x00 - List
    BINARY = 0b001000    # 0x08 - Binary
    BOOLEAN = 0b001001   # 0x09 - Boolean
    ASCII = 0b010000     # 0x10 - ASCII
    JIS8 = 0b010001      # 0x11 - JIS-8 (not commonly used)
    I8 = 0b011000        # 0x18 - 8-byte signed integer
    I1 = 0b011001        # 0x19 - 1-byte signed integer
    I2 = 0b011010        # 0x1A - 2-byte signed integer
    I4 = 0b011100        # 0x1C - 4-byte signed integer
    F8 = 0b100000        # 0x20 - 8-byte floating point
    F4 = 0b100100        # 0x24 - 4-byte floating point
    U8 = 0b101000        # 0x28 - 8-byte unsigned integer
    U1 = 0b101001        # 0x29 - 1-byte unsigned integer
    U2 = 0b101010        # 0x2A - 2-byte unsigned integer
    U4 = 0b101100        # 0x2C - 4-byte unsigned integer


# Reverse mapping for decoding
FORMAT_CODE_NAMES = {
    FormatCode.LIST: "List",
    FormatCode.BINARY: "Binary",
    FormatCode.BOOLEAN: "Boolean",
    FormatCode.ASCII: "ASCII",
    FormatCode.I1: "I1",
    FormatCode.I2: "I2",
    FormatCode.I4: "I4",
    FormatCode.I8: "I8",
    FormatCode.F4: "F4",
    FormatCode.F8: "F8",
    FormatCode.U1: "U1",
    FormatCode.U2: "U2",
    FormatCode.U4: "U4",
    FormatCode.U8: "U8",
}


# ============================================================================
# SECS-II Data Item Class
# ============================================================================

class Secs2Item:
    """
    Represents a SECS-II data item

    This is a wrapper class that holds both the value and its SECS-II type.
    """

    def __init__(self, value: Any, format_code: FormatCode = None):
        """
        Initialize SECS-II item

        Args:
            value: The actual data value
            format_code: Explicit format code (auto-detected if None)
        """
        self.value = value
        self.format_code = format_code or self._infer_format_code(value)

    def _infer_format_code(self, value: Any) -> FormatCode:
        """Automatically infer format code from Python type"""
        if isinstance(value, list):
            return FormatCode.LIST
        elif isinstance(value, bool):
            return FormatCode.BOOLEAN
        elif isinstance(value, str):
            return FormatCode.ASCII
        elif isinstance(value, bytes):
            return FormatCode.BINARY
        elif isinstance(value, float):
            return FormatCode.F4  # Default to F4 for floats
        elif isinstance(value, int):
            # Choose smallest unsigned integer type that fits
            if 0 <= value <= 255:
                return FormatCode.U1
            elif 0 <= value <= 65535:
                return FormatCode.U2
            elif 0 <= value <= 4294967295:
                return FormatCode.U4
            elif value < 0:
                # Negative - choose signed
                if -128 <= value <= 127:
                    return FormatCode.I1
                elif -32768 <= value <= 32767:
                    return FormatCode.I2
                elif -2147483648 <= value <= 2147483647:
                    return FormatCode.I4
                else:
                    return FormatCode.I8
            else:
                return FormatCode.U8
        else:
            raise ValueError(f"Cannot infer SECS-II type for {type(value)}")

    def __repr__(self):
        type_name = FORMAT_CODE_NAMES.get(self.format_code, f"Unknown(0x{self.format_code:02X})")
        if self.format_code == FormatCode.LIST:
            return f"<{type_name}[{len(self.value)}]>"
        else:
            return f"<{type_name}: {self.value}>"


# ============================================================================
# Encoding Functions
# ============================================================================

def encode(value: Any, format_code: FormatCode = None) -> bytes:
    """
    Encode a Python value to SECS-II binary format

    Args:
        value: Python value to encode (int, float, str, bytes, bool, list, dict)
        format_code: Optional explicit format code

    Returns:
        SECS-II encoded bytes

    Examples:
        >>> encode(123)
        b'\\xa9\\x01{'
        >>> encode("Hello")
        b'\\x41\\x05Hello'
        >>> encode([1, 2, 3])
        b'\\x01\\x03\\xa9\\x01\\x01\\xa9\\x01\\x02\\xa9\\x01\\x03'
    """
    item = Secs2Item(value, format_code)
    return _encode_item(item)


def _encode_item(item: Secs2Item) -> bytes:
    """Internal: Encode a Secs2Item to binary"""

    if item.format_code == FormatCode.LIST:
        return _encode_list(item.value)
    elif item.format_code == FormatCode.BINARY:
        return _encode_binary(item.value)
    elif item.format_code == FormatCode.BOOLEAN:
        return _encode_boolean(item.value)
    elif item.format_code == FormatCode.ASCII:
        return _encode_ascii(item.value)
    elif item.format_code in (FormatCode.I1, FormatCode.I2, FormatCode.I4, FormatCode.I8):
        return _encode_integer(item.value, item.format_code, signed=True)
    elif item.format_code in (FormatCode.U1, FormatCode.U2, FormatCode.U4, FormatCode.U8):
        return _encode_integer(item.value, item.format_code, signed=False)
    elif item.format_code in (FormatCode.F4, FormatCode.F8):
        return _encode_float(item.value, item.format_code)
    else:
        raise ValueError(f"Unsupported format code: {item.format_code}")


def _encode_list(items: list) -> bytes:
    """Encode a list of items"""
    # Encode all items first
    encoded_items = []
    for item in items:
        if isinstance(item, Secs2Item):
            encoded_items.append(_encode_item(item))
        else:
            encoded_items.append(encode(item))

    # Calculate total data length
    data = b''.join(encoded_items)
    data_length = len(items)  # List length is number of items, not bytes

    # Create header
    header = _create_header(FormatCode.LIST, data_length)

    return header + data


def _encode_binary(data: bytes) -> bytes:
    """Encode binary data"""
    header = _create_header(FormatCode.BINARY, len(data))
    return header + data


def _encode_boolean(value: Union[bool, List[bool]]) -> bytes:
    """Encode boolean value(s)"""
    if isinstance(value, bool):
        value = [value]

    data = bytes([1 if v else 0 for v in value])
    header = _create_header(FormatCode.BOOLEAN, len(data))
    return header + data


def _encode_ascii(text: str) -> bytes:
    """Encode ASCII string"""
    try:
        data = text.encode('ascii')
    except UnicodeEncodeError as e:
        raise ValueError(
            f"SECS-II ASCII encoding failed: string contains non-ASCII characters: {e}"
        ) from e
    header = _create_header(FormatCode.ASCII, len(data))
    return header + data


def _encode_integer(value: Union[int, List[int]], format_code: FormatCode, signed: bool) -> bytes:
    """Encode integer value(s)"""
    # Determine byte size
    size_map = {
        FormatCode.I1: 1, FormatCode.I2: 2, FormatCode.I4: 4, FormatCode.I8: 8,
        FormatCode.U1: 1, FormatCode.U2: 2, FormatCode.U4: 4, FormatCode.U8: 8,
    }
    byte_size = size_map[format_code]

    # Handle single value or list
    if isinstance(value, int):
        value = [value]

    # Pack integers using bytearray for O(n) performance
    fmt_map = {
        (1, True): '>b', (2, True): '>h', (4, True): '>i', (8, True): '>q',
        (1, False): '>B', (2, False): '>H', (4, False): '>I', (8, False): '>Q',
    }
    fmt = fmt_map[(byte_size, signed)]
    parts = [struct.pack(fmt, v) for v in value]
    data = b''.join(parts)

    header = _create_header(format_code, len(data))
    return header + data


def _encode_float(value: Union[float, List[float]], format_code: FormatCode) -> bytes:
    """Encode floating point value(s)"""
    if isinstance(value, (int, float)):
        value = [float(value)]

    fmt = '>f' if format_code == FormatCode.F4 else '>d'
    parts = [struct.pack(fmt, v) for v in value]
    data = b''.join(parts)

    header = _create_header(format_code, len(data))
    return header + data


def _create_header(format_code: FormatCode, length: int) -> bytes:
    """
    Create SECS-II item header

    Format: [Format Byte][Length Bytes]
    Format Byte: [Format Code (6 bits)][Length Bytes Count (2 bits)]
    """
    # Determine number of length bytes needed
    if length < 256:
        length_bytes_count = 1
        length_bytes = struct.pack('>B', length)
    elif length < 65536:
        length_bytes_count = 2
        length_bytes = struct.pack('>H', length)
    elif length < 16777216:
        length_bytes_count = 3
        length_bytes = struct.pack('>I', length)[1:]  # Skip first byte
    else:
        raise ValueError(f"Data length {length} exceeds maximum (16777215)")

    # Create format byte
    format_byte = (format_code << 2) | length_bytes_count

    return bytes([format_byte]) + length_bytes


# ============================================================================
# Decoding Functions
# ============================================================================

def decode(data: bytes) -> Tuple[Any, int]:
    """
    Decode SECS-II binary data to Python object

    Args:
        data: SECS-II encoded bytes

    Returns:
        Tuple of (decoded_value, bytes_consumed)

    Examples:
        >>> decode(b'\\xa9\\x01{')
        (123, 3)
        >>> decode(b'\\x41\\x05Hello')
        ('Hello', 7)
    """
    if len(data) == 0:
        raise ValueError("Cannot decode empty data")

    return _decode_item(data, 0)


def _decode_item(data: bytes, offset: int) -> Tuple[Any, int]:
    """
    Internal: Decode a single item starting at offset

    Returns:
        Tuple of (value, new_offset)
    """
    data_len = len(data)

    # Parse format byte
    if offset >= data_len:
        raise ValueError(f"SECS-II decode: unexpected end of data at offset {offset}")
    format_byte = data[offset]
    format_code = (format_byte >> 2) & 0x3F
    length_bytes_count = format_byte & 0x03

    offset += 1

    # Parse length with boundary checks
    if offset + length_bytes_count > data_len:
        raise ValueError(
            f"SECS-II decode: not enough data for length bytes at offset {offset}, "
            f"need {length_bytes_count} bytes, have {data_len - offset}"
        )
    if length_bytes_count == 0:
        length = 0
    elif length_bytes_count == 1:
        length = struct.unpack('>B', data[offset:offset+1])[0]
        offset += 1
    elif length_bytes_count == 2:
        length = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
    elif length_bytes_count == 3:
        length = struct.unpack('>I', b'\x00' + data[offset:offset+3])[0]
        offset += 3

    # Validate data length (skip for LIST where length = item count)
    if format_code != FormatCode.LIST:
        if offset + length > data_len:
            raise ValueError(
                f"SECS-II decode: declared data length {length} exceeds available data "
                f"({data_len - offset} bytes remaining) at offset {offset}"
            )

    # Decode based on format code
    if format_code == FormatCode.LIST:
        return _decode_list(data, offset, length)
    elif format_code == FormatCode.BINARY:
        return _decode_binary(data, offset, length)
    elif format_code == FormatCode.BOOLEAN:
        return _decode_boolean(data, offset, length)
    elif format_code == FormatCode.ASCII:
        return _decode_ascii(data, offset, length)
    elif format_code == FormatCode.I1:
        return _decode_integer(data, offset, length, 1, True)
    elif format_code == FormatCode.I2:
        return _decode_integer(data, offset, length, 2, True)
    elif format_code == FormatCode.I4:
        return _decode_integer(data, offset, length, 4, True)
    elif format_code == FormatCode.I8:
        return _decode_integer(data, offset, length, 8, True)
    elif format_code == FormatCode.U1:
        return _decode_integer(data, offset, length, 1, False)
    elif format_code == FormatCode.U2:
        return _decode_integer(data, offset, length, 2, False)
    elif format_code == FormatCode.U4:
        return _decode_integer(data, offset, length, 4, False)
    elif format_code == FormatCode.U8:
        return _decode_integer(data, offset, length, 8, False)
    elif format_code == FormatCode.F4:
        return _decode_float(data, offset, length, 4)
    elif format_code == FormatCode.F8:
        return _decode_float(data, offset, length, 8)
    else:
        raise ValueError(f"Unknown format code: 0x{format_code:02X}")


def _decode_list(data: bytes, offset: int, item_count: int) -> Tuple[list, int]:
    """Decode a list of items"""
    items = []
    for _ in range(item_count):
        value, offset = _decode_item(data, offset)
        items.append(value)
    return items, offset


def _decode_binary(data: bytes, offset: int, length: int) -> Tuple[bytes, int]:
    """Decode binary data"""
    return data[offset:offset+length], offset + length


def _decode_boolean(data: bytes, offset: int, length: int) -> Tuple[Union[bool, List[bool]], int]:
    """Decode boolean value(s)"""
    values = [bool(b) for b in data[offset:offset+length]]
    if len(values) == 1:
        return values[0], offset + length
    return values, offset + length


def _decode_ascii(data: bytes, offset: int, length: int) -> Tuple[str, int]:
    """Decode ASCII string"""
    try:
        text = data[offset:offset+length].decode('ascii')
    except UnicodeDecodeError:
        # Fallback: replace non-ASCII bytes rather than crashing
        text = data[offset:offset+length].decode('ascii', errors='replace')
        import logging
        logging.getLogger(__name__).warning(
            f"SECS-II ASCII decode: non-ASCII bytes at offset {offset}, using replacement"
        )
    return text, offset + length


def _decode_integer(data: bytes, offset: int, length: int, byte_size: int, signed: bool) -> Tuple[Union[int, List[int]], int]:
    """Decode integer value(s)"""
    count = length // byte_size
    values = []

    for i in range(count):
        pos = offset + (i * byte_size)
        if signed:
            if byte_size == 1:
                values.append(struct.unpack('>b', data[pos:pos+1])[0])
            elif byte_size == 2:
                values.append(struct.unpack('>h', data[pos:pos+2])[0])
            elif byte_size == 4:
                values.append(struct.unpack('>i', data[pos:pos+4])[0])
            elif byte_size == 8:
                values.append(struct.unpack('>q', data[pos:pos+8])[0])
        else:
            if byte_size == 1:
                values.append(struct.unpack('>B', data[pos:pos+1])[0])
            elif byte_size == 2:
                values.append(struct.unpack('>H', data[pos:pos+2])[0])
            elif byte_size == 4:
                values.append(struct.unpack('>I', data[pos:pos+4])[0])
            elif byte_size == 8:
                values.append(struct.unpack('>Q', data[pos:pos+8])[0])

    if len(values) == 1:
        return values[0], offset + length
    return values, offset + length


def _decode_float(data: bytes, offset: int, length: int, byte_size: int) -> Tuple[Union[float, List[float]], int]:
    """Decode floating point value(s)"""
    count = length // byte_size
    values = []

    for i in range(count):
        pos = offset + (i * byte_size)
        if byte_size == 4:
            values.append(struct.unpack('>f', data[pos:pos+4])[0])
        elif byte_size == 8:
            values.append(struct.unpack('>d', data[pos:pos+8])[0])

    if len(values) == 1:
        return values[0], offset + length
    return values, offset + length


# ============================================================================
# High-Level Helper Functions
# ============================================================================

def encode_message(data: dict) -> bytes:
    """
    Encode a dictionary as a SECS-II message

    The dictionary is converted to a list of alternating keys and values.

    Args:
        data: Dictionary to encode

    Returns:
        SECS-II encoded bytes

    Example:
        >>> msg = {"MDLN": "AMAT", "SOFTREV": "1.2.3"}
        >>> encoded = encode_message(msg)
    """
    # Convert dict to list format
    items = []
    for key, value in data.items():
        items.append(key)  # Key as ASCII
        items.append(value)  # Value (auto-typed)

    return encode(items)


def decode_message(data: bytes) -> dict:
    """
    Decode SECS-II message to dictionary

    Assumes the message is a list of alternating keys (ASCII) and values.

    Args:
        data: SECS-II encoded bytes

    Returns:
        Decoded dictionary

    Example:
        >>> data = b'...'  # SECS-II encoded
        >>> msg = decode_message(data)
        >>> print(msg)
        {'MDLN': 'AMAT', 'SOFTREV': '1.2.3'}
    """
    items, _ = decode(data)

    if not isinstance(items, list):
        raise ValueError("Expected list format for message")

    if len(items) % 2 != 0:
        raise ValueError("Message must have even number of items (key-value pairs)")

    result = {}
    for i in range(0, len(items), 2):
        key = items[i]
        value = items[i + 1]

        if not isinstance(key, str):
            raise ValueError(f"Expected string key, got {type(key)}")

        result[key] = value

    return result


# ============================================================================
# Utility Functions
# ============================================================================

def format_bytes(data: bytes, bytes_per_line: int = 16) -> str:
    """
    Format bytes for display (hex dump)

    Args:
        data: Bytes to format
        bytes_per_line: Number of bytes per line

    Returns:
        Formatted string
    """
    lines = []
    for i in range(0, len(data), bytes_per_line):
        chunk = data[i:i+bytes_per_line]
        hex_part = ' '.join(f'{b:02X}' for b in chunk)
        ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        lines.append(f"{i:04X}  {hex_part:<{bytes_per_line*3}}  {ascii_part}")
    return '\n'.join(lines)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    print("="*80)
    print("SECS-II Codec Examples")
    print("="*80)

    # Example 1: Encode simple values
    print("\n1. Encode simple values:")
    print(f"   Integer 123: {encode(123).hex()}")
    print(f"   Float 3.14: {encode(3.14).hex()}")
    print(f"   String 'Hello': {encode('Hello').hex()}")
    print(f"   Boolean True: {encode(True).hex()}")

    # Example 2: Encode list
    print("\n2. Encode list:")
    data = [1, 2, 3, "test", 4.5]
    encoded = encode(data)
    print(f"   Data: {data}")
    print(f"   Encoded: {encoded.hex()}")

    # Example 3: Decode
    print("\n3. Decode:")
    decoded, _ = decode(encoded)
    print(f"   Decoded: {decoded}")

    # Example 4: Nested structure
    print("\n4. Nested structure:")
    nested = {
        "MDLN": "AMAT Centura",
        "SOFTREV": "1.2.3",
        "PARAMS": [
            {"TEMP": 650.5},
            {"PRESSURE": 5.2}
        ]
    }
    # Convert to list format
    msg_list = [
        "MDLN", "AMAT Centura",
        "SOFTREV", "1.2.3",
        "PARAMS", [
            ["TEMP", 650.5],
            ["PRESSURE", 5.2]
        ]
    ]
    encoded = encode(msg_list)
    print(f"   Encoded length: {len(encoded)} bytes")
    print(f"   Hex dump:")
    print(format_bytes(encoded))

    decoded, _ = decode(encoded)
    print(f"\n   Decoded: {decoded}")

    print("\n" + "="*80)
    print("All examples completed successfully!")
    print("="*80)
