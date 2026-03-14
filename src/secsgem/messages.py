"""
Message Builder
===============

This module builds SECS-II messages dynamically based on equipment configuration.
It provides template-based message construction with parameter validation.

Features:
    - Build messages from YAML definitions
    - Parameter validation and type checking
    - Template support with placeholders
    - Default value handling
    - Nested message construction

Usage:
    builder = MessageBuilder(config)

    # Build simple message
    msg_data = builder.build("S1F1")

    # Build message with parameters
    msg_data = builder.build("S2F41", {
        "RCMD": "START",
        "PARAMS": {"TEMP": 650.0, "PRESSURE": 5.5}
    })
"""

import logging
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from .config import EquipmentConfiguration, MessageDefinition
from .secs2 import encode, FormatCode


logger = logging.getLogger(__name__)


# ============================================================================
# Message Builder
# ============================================================================

class MessageBuilder:
    """
    SECS Message Builder

    Builds SECS-II messages based on equipment configuration definitions.
    Handles parameter validation, type conversion, and encoding.
    """

    def __init__(self, config: EquipmentConfiguration):
        """
        Initialize message builder

        Args:
            config: Equipment configuration
        """
        self.config = config
        logger.info(f"MessageBuilder initialized for {config.equipment.type}")

    def build(self, message_name: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Build a SECS message

        Args:
            message_name: Message name (e.g., "S1F1", "S2F41")
            params: Message parameters (optional)

        Returns:
            SECS-II encoded message body

        Raises:
            ValueError: If message definition not found or parameters invalid

        Examples:
            >>> builder = MessageBuilder(config)
            >>> data = builder.build("S1F1")
            >>> data = builder.build("S2F41", {"RCMD": "START"})
        """
        # Get message definition
        msg_def = self.config.get_message_definition(message_name)
        if not msg_def:
            raise ValueError(f"Message definition not found: {message_name}")

        logger.debug(f"Building message: {message_name}")

        # Build message structure
        message_data = self._build_message_structure(msg_def, params or {})

        # Encode to SECS-II binary
        encoded = encode(message_data) if message_data is not None else b''

        logger.debug(f"Message {message_name} built: {len(encoded)} bytes")

        return encoded

    def _build_message_structure(
        self,
        msg_def: MessageDefinition,
        params: Dict[str, Any]
    ) -> Optional[Union[List, str, int, float]]:
        """Build message structure from definition and parameters"""

        # If no structure defined, return None (empty message)
        if not msg_def.structure:
            return None

        # Build list of items based on structure
        items = []

        for item_def in msg_def.structure:
            item_name = item_def.name
            item_type = item_def.type
            item_desc = item_def.description

            # Get value from params
            if item_name in params:
                value = params[item_name]
            else:
                # Use default or raise error
                value = self._get_default_value(item_type, item_name)

            # Convert value to appropriate type
            converted_value = self._convert_value(value, item_type, item_name)

            items.append(converted_value)

        # If single item, return it directly
        if len(items) == 1:
            return items[0]

        return items

    def _convert_value(self, value: Any, expected_type: str, item_name: str) -> Any:
        """
        Convert value to expected SECS-II type

        Args:
            value: Raw value
            expected_type: Expected SECS-II type (ASCII, U4, F4, LIST, etc.)
            item_name: Item name (for error messages)

        Returns:
            Converted value
        """
        type_upper = expected_type.upper()

        # Handle LIST type
        if type_upper == 'LIST':
            if not isinstance(value, (list, dict)):
                raise ValueError(f"{item_name}: Expected list or dict, got {type(value)}")
            return value if isinstance(value, list) else self._dict_to_list(value)

        # Handle ASCII type
        elif type_upper == 'ASCII':
            return str(value)

        # Handle BINARY type
        elif type_upper == 'BINARY':
            if isinstance(value, bytes):
                return value
            elif isinstance(value, int):
                return bytes([value])
            else:
                raise ValueError(f"{item_name}: Cannot convert {type(value)} to BINARY")

        # Handle BOOLEAN type
        elif type_upper == 'BOOLEAN':
            return bool(value)

        # Handle integer types (I1, I2, I4, I8, U1, U2, U4, U8)
        elif type_upper in ['I1', 'I2', 'I4', 'I8', 'U1', 'U2', 'U4', 'U8']:
            if isinstance(value, (list, tuple)):
                return [int(v) for v in value]
            return int(value)

        # Handle float types (F4, F8)
        elif type_upper in ['F4', 'F8']:
            if isinstance(value, (list, tuple)):
                return [float(v) for v in value]
            return float(value)

        else:
            # Unknown type, return as-is
            logger.warning(f"Unknown type {expected_type} for {item_name}, using as-is")
            return value

    def _dict_to_list(self, data: Dict[str, Any]) -> List:
        """Convert dictionary to alternating key-value list"""
        items = []
        for key, value in data.items():
            items.append(str(key))
            items.append(value)
        return items

    def _get_default_value(self, item_type: str, item_name: str):
        """Get default value for a data type"""
        type_upper = item_type.upper()

        if type_upper == 'LIST':
            return []
        elif type_upper == 'ASCII':
            return ""
        elif type_upper == 'BINARY':
            return b''
        elif type_upper == 'BOOLEAN':
            return False
        elif type_upper in ['I1', 'I2', 'I4', 'I8', 'U1', 'U2', 'U4', 'U8']:
            return 0
        elif type_upper in ['F4', 'F8']:
            return 0.0
        else:
            raise ValueError(f"Cannot determine default value for {item_name} (type: {item_type})")

    # ------------------------------------------------------------------------
    # High-Level Message Building Methods
    # ------------------------------------------------------------------------

    def build_s1f1(self) -> bytes:
        """Build S1F1 (Are You There Request) - always empty"""
        return self.build("S1F1")

    def build_s1f2(self, model: str, software_rev: str) -> bytes:
        """
        Build S1F2 (Are You There Response)

        Args:
            model: Equipment model name
            software_rev: Software revision

        Returns:
            Encoded S1F2 message
        """
        return self.build("S1F2", {
            "MDLN": model,
            "SOFTREV": software_rev
        })

    def build_s1f3(self, svids: List[int]) -> bytes:
        """
        Build S1F3 (Selected Equipment Status Request)

        Args:
            svids: List of Status Variable IDs to request

        Returns:
            Encoded S1F3 message
        """
        return self.build("S1F3", {
            "SVID": svids
        })

    def build_s1f13(self) -> bytes:
        """Build S1F13 (Establish Communications Request)"""
        return self.build("S1F13")

    def build_s1f14(self, commack: int, model_data: List[str]) -> bytes:
        """
        Build S1F14 (Establish Communications Acknowledge)

        Args:
            commack: Communication acknowledge code (0=success)
            model_data: List of equipment model information

        Returns:
            Encoded S1F14 message
        """
        return self.build("S1F14", {
            "COMMACK": commack,
            "MDLN": model_data
        })

    def build_s2f41(self, rcmd: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """
        Build S2F41 (Remote Command Send)

        Args:
            rcmd: Remote command name
            params: Command parameters (optional)

        Returns:
            Encoded S2F41 message
        """
        # Validate command exists
        cmd_def = self.config.get_command(rcmd)
        if not cmd_def:
            raise ValueError(f"Unknown command: {rcmd}")

        # Validate required parameters
        if params is None:
            params = {}

        for param_def in cmd_def.parameters:
            if param_def.required and param_def.name not in params:
                raise ValueError(f"Required parameter missing: {param_def.name}")

        # Convert params dict to list format
        param_list = []
        for param_def in cmd_def.parameters:
            if param_def.name in params:
                param_list.append(params[param_def.name])

        return self.build("S2F41", {
            "RCMD": rcmd,
            "PARAMS": param_list
        })

    def build_s2f42(self, hcack: int, return_params: Optional[List[Any]] = None) -> bytes:
        """
        Build S2F42 (Remote Command Acknowledge)

        Args:
            hcack: Host command acknowledge code
            return_params: Return parameters (optional)

        Returns:
            Encoded S2F42 message
        """
        return self.build("S2F42", {
            "HCACK": hcack,
            "PARAMS": return_params or []
        })

    def build_s6f11(self, dataid: int, ceid: int, reports: List[List[Any]]) -> bytes:
        """
        Build S6F11 (Event Report Send)

        Args:
            dataid: Data ID
            ceid: Collection Event ID
            reports: List of reports (each report is a list of values)

        Returns:
            Encoded S6F11 message
        """
        return self.build("S6F11", {
            "DATAID": dataid,
            "CEID": ceid,
            "RPT": reports
        })

    def build_s6f12(self, ackc6: int) -> bytes:
        """
        Build S6F12 (Event Report Acknowledge)

        Args:
            ackc6: Acknowledge code

        Returns:
            Encoded S6F12 message
        """
        return self.build("S6F12", {
            "ACKC6": ackc6
        })

    # ------------------------------------------------------------------------
    # Report Building
    # ------------------------------------------------------------------------

    def build_report(self, report_id: int, variable_values: Dict[int, Any]) -> List[Any]:
        """
        Build a report from variable values

        Args:
            report_id: Report ID
            variable_values: Dictionary mapping SVID to value

        Returns:
            List of values in report order
        """
        report_def = self.config.get_report(report_id)
        if not report_def:
            raise ValueError(f"Unknown report: {report_id}")

        report_values = []
        for svid in report_def.variables:
            if svid not in variable_values:
                # Use default value
                var_def = self.config.get_data_variable(svid)
                if var_def:
                    default = self._get_default_for_variable(var_def.type)
                    report_values.append(default)
                else:
                    raise ValueError(f"Variable {svid} not found and no value provided")
            else:
                report_values.append(variable_values[svid])

        return report_values

    def _get_default_for_variable(self, var_type: str) -> Any:
        """Get default value for a variable type"""
        if var_type in ['I1', 'I2', 'I4', 'I8', 'U1', 'U2', 'U4', 'U8']:
            return 0
        elif var_type in ['F4', 'F8']:
            return 0.0
        elif var_type == 'ASCII':
            return ""
        elif var_type == 'BOOLEAN':
            return False
        else:
            return None

    # ------------------------------------------------------------------------
    # Utility Methods
    # ------------------------------------------------------------------------

    def get_message_info(self, message_name: str) -> Dict[str, Any]:
        """
        Get information about a message

        Args:
            message_name: Message name (e.g., "S1F1")

        Returns:
            Dictionary with message information
        """
        msg_def = self.config.get_message_definition(message_name)
        if not msg_def:
            return {}

        return {
            'stream': msg_def.stream,
            'function': msg_def.function,
            'wait_bit': msg_def.wait_bit,
            'description': msg_def.description,
            'has_structure': msg_def.structure is not None,
            'structure_items': len(msg_def.structure) if msg_def.structure else 0
        }

    def list_available_messages(self) -> List[str]:
        """Get list of all available message names"""
        return list(self.config.messages.keys())

    def list_available_commands(self) -> List[str]:
        """Get list of all available remote commands"""
        return list(self.config.commands.keys())


# ============================================================================
# Helper Functions
# ============================================================================

def build_timestamp() -> str:
    """Build current timestamp in standard format"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_status_report(config: EquipmentConfiguration, status_data: Dict[str, Any]) -> List:
    """
    Build a standard equipment status report

    Args:
        config: Equipment configuration
        status_data: Status data dictionary

    Returns:
        Status report as list
    """
    return [
        "CLOCK", status_data.get("CLOCK", build_timestamp()),
        "CONTROL_STATE", status_data.get("CONTROL_STATE", 2),  # ONLINE_REMOTE
        "PROCESSING_STATE", status_data.get("PROCESSING_STATE", 1),  # IDLE
    ]


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("="*80)
    print("Message Builder Test")
    print("="*80)

    # Find project root
    project_root = Path(__file__).parent.parent.parent

    # Import config loader
    from .config import ConfigLoader

    # Load AMAT config
    loader = ConfigLoader()
    config_path = str(project_root / "configs" / "amat_centura.yaml")

    try:
        config = loader.load(config_path)
        print(f"\n✅ Loaded configuration: {config.equipment.type}")

        # Create message builder
        builder = MessageBuilder(config)
        print(f"✅ Message builder created")

        # List available messages
        print(f"\n📨 Available Messages:")
        for msg_name in builder.list_available_messages()[:10]:  # Show first 10
            info = builder.get_message_info(msg_name)
            print(f"   {msg_name}: {info['description']}")

        # Build S1F1
        print(f"\n📤 Building S1F1 (Are You There):")
        s1f1_data = builder.build_s1f1()
        print(f"   Encoded: {s1f1_data.hex()} ({len(s1f1_data)} bytes)")

        # Build S1F13
        print(f"\n📤 Building S1F13 (Establish Communications):")
        s1f13_data = builder.build_s1f13()
        print(f"   Encoded: {s1f13_data.hex()} ({len(s1f13_data)} bytes)")

        # Build S2F41 (Remote Command)
        print(f"\n📤 Building S2F41 (START_DEPOSITION command):")
        s2f41_data = builder.build_s2f41("START_DEPOSITION", {
            "RECIPE_ID": "ALU_SPUTTER_001",
            "LOT_ID": "LOT-2025-001",
            "WAFER_ID": "WAFER-001"
        })
        print(f"   Encoded: {len(s2f41_data)} bytes")
        from .secs2 import format_bytes
        print(f"   Hex dump:")
        print(format_bytes(s2f41_data))

        # Build S6F11 (Event Report)
        print(f"\n📤 Building S6F11 (Event Report - Process Start):")

        # Build reports
        report_1 = ["2025-01-03 14:30:00", 2, 3]  # Equipment status
        report_2 = [5.1, 8500.0, 425.5, 250.0, 45.2, 1500.0]  # Process params

        s6f11_data = builder.build_s6f11(
            dataid=1001,
            ceid=100,  # PROCESS_START
            reports=[report_1, report_2]
        )
        print(f"   Encoded: {len(s6f11_data)} bytes")

        print("\n" + "="*80)
        print("✅ Message builder test completed successfully!")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
