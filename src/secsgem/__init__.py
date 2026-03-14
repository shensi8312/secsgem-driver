"""
SECS/GEM Driver
===============

Configuration-driven SECS/GEM driver for semiconductor equipment communication.

Modules:
    hsms: HSMS protocol implementation (SEMI E37)
    secs2: SECS-II codec (SEMI E5)
    config: Equipment configuration loader
    messages: Message builder
    driver: High-level driver API
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

__version__ = "1.0.0"

__all__ = [
    # HSMS
    'HSMSConnection', 'HSMSHeader', 'HSMSMessageType',
    'HSMSSelectStatus', 'HSMSDeselectStatus', 'HSMSRejectReason',
    # SECS-II
    'encode', 'decode', 'encode_message', 'decode_message',
    'Secs2Item', 'FormatCode', 'format_bytes',
    # Config
    'ConfigLoader', 'EquipmentConfiguration',
    # Messages
    'MessageBuilder',
    # Driver
    'SecsGemDriver',
]
