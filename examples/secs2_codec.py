#!/usr/bin/env python3
"""
SECS-II Codec Example
======================

Demonstrates encoding and decoding of SECS-II messages
per SEMI E5 standard.

Usage:
    python examples/secs2_codec.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from secsgem import encode, decode, format_bytes, FormatCode, Secs2Item


def main():
    print("=" * 60)
    print("SECS-II Codec Examples")
    print("=" * 60)

    # 1. Basic types
    print("\n--- Basic Type Encoding ---")
    for label, value in [
        ("Integer 42", 42),
        ("Float 3.14", 3.14),
        ("String 'AMAT'", "AMAT"),
        ("Boolean True", True),
        ("Binary", b"\x01\x02\x03"),
    ]:
        encoded = encode(value)
        decoded_val, _ = decode(encoded)
        print(f"  {label:20s} -> {encoded.hex()} -> {decoded_val}")

    # 2. List (nested structure)
    print("\n--- List Encoding ---")
    data = ["MDLN", "Centura 5200", "SOFTREV", "1.2.3"]
    encoded = encode(data)
    decoded_val, _ = decode(encoded)
    print(f"  Input:   {data}")
    print(f"  Encoded: {len(encoded)} bytes")
    print(f"  Decoded: {decoded_val}")

    # 3. Explicit format codes
    print("\n--- Explicit Format Codes ---")
    item = Secs2Item(42, FormatCode.U4)  # Force 4-byte unsigned
    print(f"  U4(42): {encode(item.value, item.format_code).hex()}")

    item = Secs2Item(3.14, FormatCode.F8)  # Force 8-byte float
    print(f"  F8(3.14): {encode(item.value, item.format_code).hex()}")

    # 4. Hex dump
    print("\n--- Hex Dump ---")
    msg = encode(["RECIPE_ID", "ALU_001", "TEMP", 650.5, "PRESSURE", 5.2])
    print(format_bytes(msg))

    print("\n" + "=" * 60)
    print("All examples completed")


if __name__ == "__main__":
    main()
