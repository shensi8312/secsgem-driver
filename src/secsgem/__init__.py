"""
Early SECS/GEM prototyping resources.

This package is for learning, simulator work, and integration evaluation. It is
not a production-certified SECS/GEM or GEM300 solution.
"""

from .hsms import (
    HSMSConnection,
    HSMSHeader,
    HSMSMessageType,
    HSMSSelectStatus,
    HSMSDeselectStatus,
    HSMSRejectReason,
)
from .secs2 import (
    encode,
    decode,
    encode_message,
    decode_message,
    Secs2Item,
    FormatCode,
    format_bytes,
)
from .config import (
    ConfigLoader,
    EquipmentConfiguration,
)
from .messages import MessageBuilder
from .driver import SecsGemDriver

__version__ = "0.1.0"

__all__ = [
    "HSMSConnection", "HSMSHeader", "HSMSMessageType",
    "HSMSSelectStatus", "HSMSDeselectStatus", "HSMSRejectReason",
    "encode", "decode", "encode_message", "decode_message",
    "Secs2Item", "FormatCode", "format_bytes",
    "ConfigLoader", "EquipmentConfiguration",
    "MessageBuilder", "SecsGemDriver",
]
