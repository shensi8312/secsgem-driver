"""
Unified SECS/GEM Driver API
============================

This module provides a high-level, unified API for SECS/GEM equipment communication.
It integrates all core modules and provides a simple interface for equipment control.

Features:
    - Simple connection management
    - Automatic message building from configuration
    - Event subscription and handling
    - Status monitoring
    - Configuration hot-swapping
    - Auto-reconnection
    - Comprehensive error handling

Usage:
    # Initialize driver with configuration file
    driver = SecsGemDriver("configs/amat_centura.yaml")

    # Connect to equipment
    await driver.connect()

    # Send messages
    response = await driver.send("S1F1")

    # Send commands
    await driver.send_command("START", {
        "RECIPE_ID": "ALU_001",
        "LOT_ID": "LOT-001"
    })

    # Subscribe to events
    @driver.on_event(100)  # PROCESS_START
    async def handle_process_start(event_data):
        print(f"Process started: {event_data}")

    # Disconnect
    await driver.disconnect()
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from pathlib import Path
from datetime import datetime

from .hsms import HSMSConnection, HSMSHeader
from .secs2 import decode, encode
from .config import ConfigLoader, EquipmentConfiguration
from .messages import MessageBuilder


logger = logging.getLogger(__name__)


# ============================================================================
# Unified SECS/GEM Driver
# ============================================================================

class SecsGemDriver:
    """
    Unified SECS/GEM Equipment Driver

    High-level API for SECS/GEM equipment communication.
    Handles connection, messaging, and event processing automatically.
    """

    def __init__(self, config_path: str, auto_connect: bool = False):
        """
        Initialize SECS/GEM driver

        Args:
            config_path: Path to YAML configuration file
            auto_connect: Automatically connect after initialization

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        # Load configuration
        self.config_path = Path(config_path)
        self.config_loader = ConfigLoader()
        self.config = self.config_loader.load(str(self.config_path))

        if not self.config.is_valid():
            raise ValueError(f"Invalid configuration: {config_path}")

        # Create message builder
        self.message_builder = MessageBuilder(self.config)

        # Create HSMS connection
        conn_params = self.config.get_connection_params()
        self.connection = HSMSConnection(**conn_params)

        # Set up message handler
        self.connection.on_message_received = self._handle_message
        self.connection.on_connection_lost = self._handle_connection_lost

        # Event handlers
        self._event_handlers: Dict[int, List[Callable]] = {}

        # Status
        self.connected = False
        self.selected = False
        self._auto_reconnect = self.config.settings.auto_reconnect
        self._reconnect_task: Optional[asyncio.Task] = None

        # Statistics
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'events_received': 0,
            'errors': 0,
            'connected_since': None,
            'last_message_time': None
        }

        logger.info(f"SecsGemDriver initialized for {self.config.equipment.type}")

        # Auto-connect if requested
        if auto_connect:
            asyncio.create_task(self.connect())

    # ------------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------------

    async def connect(self) -> bool:
        """
        Connect to equipment

        Returns:
            True if connection successful, False otherwise
        """
        if self.connected:
            logger.warning("Already connected")
            return True

        logger.info(f"Connecting to {self.config.equipment.type} at "
                   f"{self.config.connection.ip_address}:{self.config.connection.port}")

        try:
            # Establish HSMS connection
            if not await self.connection.connect():
                logger.error("HSMS connection failed")
                return False

            self.connected = True
            self.selected = self.connection.selected

            # Start heartbeat
            if self.config.settings.heartbeat_enabled:
                await self.connection.start_heartbeat(
                    interval=self.config.settings.heartbeat_interval
                )

            # Update statistics (use isoformat for JSON serialization)
            self.stats['connected_since'] = datetime.now().isoformat()

            logger.info(f"✅ Connected to {self.config.equipment.type}")

            # Send S1F13 (Establish Communications)
            try:
                await self.send("S1F13")
                logger.info("✅ Communications established (S1F13/F14)")
            except Exception as e:
                logger.warning(f"S1F13 failed (non-critical): {e}")

            return True

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self.connected = False
            return False

    async def disconnect(self):
        """Disconnect from equipment"""
        if not self.connected:
            return

        logger.info(f"Disconnecting from {self.config.equipment.type}")

        # Cancel reconnect task if running
        if self._reconnect_task:
            self._reconnect_task.cancel()
            self._reconnect_task = None

        # Disconnect HSMS
        await self.connection.disconnect()

        self.connected = False
        self.selected = False

        logger.info("Disconnected")

    async def _handle_connection_lost(self):
        """Handle connection lost event"""
        logger.error("Connection lost to equipment")

        self.connected = False
        self.selected = False

        # Auto-reconnect if enabled
        if self._auto_reconnect and not self._reconnect_task:
            logger.info("Auto-reconnect enabled, attempting reconnection...")
            self._reconnect_task = asyncio.create_task(self._auto_reconnect_loop())

    async def _auto_reconnect_loop(self):
        """Auto-reconnection loop"""
        attempt = 0
        max_attempts = self.config.settings.max_reconnect_attempts

        while not self.connected:
            attempt += 1

            # Check max attempts
            if max_attempts > 0 and attempt > max_attempts:
                logger.error(f"Max reconnection attempts ({max_attempts}) reached")
                break

            logger.info(f"Reconnection attempt {attempt}...")

            try:
                if await self.connect():
                    logger.info("✅ Reconnection successful")
                    self._reconnect_task = None
                    return
            except Exception as e:
                logger.error(f"Reconnection attempt {attempt} failed: {e}")

            # Wait before next attempt
            await asyncio.sleep(self.config.settings.reconnect_interval)

        self._reconnect_task = None

    # ------------------------------------------------------------------------
    # Message Sending
    # ------------------------------------------------------------------------

    async def send(self, message_name: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Send a SECS message

        Args:
            message_name: Message name (e.g., "S1F1", "S2F41")
            params: Message parameters (optional)

        Returns:
            Decoded reply if W-Bit set, None otherwise

        Raises:
            RuntimeError: If not connected
            ValueError: If message definition not found
            asyncio.TimeoutError: If reply timeout

        Examples:
            >>> await driver.send("S1F1")
            {'MDLN': 'AMAT Centura', 'SOFTREV': '1.2.3'}

            >>> await driver.send("S2F41", {
            ...     "RCMD": "START",
            ...     "PARAMS": {"TEMP": 650.0}
            ... })
        """
        if not self.connected:
            raise RuntimeError("Not connected to equipment")

        # Get message definition
        msg_def = self.config.get_message_definition(message_name)
        if not msg_def:
            raise ValueError(f"Unknown message: {message_name}")

        logger.debug(f"Sending {message_name}")

        # Build message data
        try:
            message_data = self.message_builder.build(message_name, params)
        except Exception as e:
            logger.error(f"Failed to build message {message_name}: {e}")
            raise

        # Send via HSMS
        try:
            reply = await self.connection.send_data_message(
                stream=msg_def.stream,
                function=msg_def.function,
                wait_bit=msg_def.wait_bit,
                data=message_data
            )

            self.stats['messages_sent'] += 1
            self.stats['last_message_time'] = datetime.now()

            # Decode reply if received
            if reply:
                reply_header, reply_data = reply
                logger.debug(f"Received reply: {reply_header}")

                # Decode SECS-II data
                if reply_data:
                    decoded, _ = decode(reply_data)
                    return self._format_reply(decoded)
                else:
                    return None

            return None

        except Exception as e:
            self.stats['errors'] += 1
            logger.error(f"Failed to send {message_name}: {e}")
            raise

    async def send_command(self, command_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send a remote command (S2F41)

        Args:
            command_name: Command name (e.g., "START", "STOP")
            params: Command parameters

        Returns:
            Command acknowledgement

        Raises:
            ValueError: If command not defined
            RuntimeError: If command rejected

        Examples:
            >>> await driver.send_command("START", {
            ...     "RECIPE_ID": "ALU_001",
            ...     "LOT_ID": "LOT-001"
            ... })
            {'HCACK': 0, 'STATUS': 'OK'}
        """
        # Validate command exists
        cmd_def = self.config.get_command(command_name)
        if not cmd_def:
            raise ValueError(f"Unknown command: {command_name}")

        logger.info(f"Sending command: {command_name}")

        # Send S2F41
        reply = await self.send("S2F41", {
            "RCMD": command_name,
            "PARAMS": params or {}
        })

        # Parse S2F42 reply
        if reply:
            hcack = reply.get('HCACK', -1)
            if hcack == 0:
                logger.info(f"✅ Command {command_name} acknowledged")
            else:
                logger.error(f"❌ Command {command_name} rejected (HCACK={hcack})")
                raise RuntimeError(f"Command rejected: HCACK={hcack}")

        return reply or {}

    async def send_raw(self, stream: int, function: int, data: Any, wait_bit: bool = True) -> Optional[Any]:
        """
        Send raw SECS message

        Args:
            stream: Stream number
            function: Function number
            data: Message data (will be encoded)
            wait_bit: Wait for reply

        Returns:
            Decoded reply data if wait_bit=True

        Examples:
            >>> await driver.send_raw(1, 1, None, wait_bit=True)
        """
        from .secs2 import encode

        if not self.connected:
            raise RuntimeError("Not connected")

        # Encode data
        encoded = encode(data) if data is not None else b''

        # Send
        reply = await self.connection.send_data_message(
            stream=stream,
            function=function,
            wait_bit=wait_bit,
            data=encoded
        )

        if reply:
            _, reply_data = reply
            if reply_data:
                decoded, _ = decode(reply_data)
                return decoded

        return None

    # ------------------------------------------------------------------------
    # Event Handling
    # ------------------------------------------------------------------------

    def on_event(self, ceid: int):
        """
        Decorator for event subscription

        Args:
            ceid: Collection Event ID

        Examples:
            >>> @driver.on_event(100)
            >>> async def handle_process_start(event_data):
            ...     print(f"Process started: {event_data}")
        """
        def decorator(func: Callable):
            self.subscribe_event(ceid, func)
            return func
        return decorator

    def subscribe_event(self, ceid: int, callback: Callable):
        """
        Subscribe to equipment event

        Args:
            ceid: Collection Event ID
            callback: Async callback function

        Examples:
            >>> async def on_alarm(data):
            ...     print(f"Alarm: {data}")
            >>> driver.subscribe_event(200, on_alarm)
        """
        if ceid not in self._event_handlers:
            self._event_handlers[ceid] = []

        self._event_handlers[ceid].append(callback)
        logger.info(f"Subscribed to event {ceid}")

    def unsubscribe_event(self, ceid: int, callback: Optional[Callable] = None):
        """
        Unsubscribe from event

        Args:
            ceid: Collection Event ID
            callback: Specific callback to remove (or None for all)
        """
        if ceid in self._event_handlers:
            if callback:
                try:
                    self._event_handlers[ceid].remove(callback)
                except ValueError:
                    logger.warning(f"Callback not found for CEID {ceid}")
            else:
                del self._event_handlers[ceid]

    async def _send_reply(self, original_header: HSMSHeader, reply_function: int, reply_data: Any = None):
        """Send a reply message with matching system_bytes"""
        try:
            encoded = encode(reply_data) if reply_data is not None else b''
            await self.connection.send_reply(
                original_header,
                reply_stream=original_header.stream & 0x7F,
                reply_function=reply_function,
                data=encoded
            )
        except Exception as e:
            logger.error(f"Failed to send reply S{original_header.stream & 0x7F}F{reply_function}: {e}")

    async def _handle_message(self, header: HSMSHeader, data: bytes):
        """Internal: Handle incoming primary message"""
        self.stats['messages_received'] += 1
        self.stats['last_message_time'] = datetime.now().isoformat()

        logger.debug(f"Received primary message: {header}")

        # Decode message data
        try:
            decoded_data = None
            if data:
                decoded_data, _ = decode(data)

            stream = header.stream & 0x7F

            # Handle S1F1 (Are You There) - auto reply with S1F2
            if stream == 1 and header.function == 1:
                if header.w_bit:
                    await self._send_reply(header, 2, [
                        self.config.equipment.type or "",
                        "1.0.0"
                    ])

            # Handle S6F11 (Event Report)
            elif stream == 6 and header.function == 11:
                await self._handle_event_report(header, decoded_data)

            # Handle S5F1 (Alarm Report)
            elif stream == 5 and header.function == 1:
                await self._handle_alarm_report(header, decoded_data)

            # For any other W-bit message, send a generic ack
            elif header.w_bit:
                await self._send_reply(header, header.function + 1, 0)

        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.stats['errors'] += 1

    async def _handle_alarm_report(self, header: HSMSHeader, data: Any):
        """Handle S5F1 (Alarm Report)"""
        # Format: [ALCD, ALID, ALTX]
        if not isinstance(data, list) or len(data) < 3:
            logger.error("Invalid S5F1 format")
            return

        alcd = data[0]  # Alarm Code (bit 8 set = alarm set, clear = alarm cleared)
        alid = data[1]  # Alarm ID
        altx = data[2]  # Alarm Text

        logger.warning(f"Alarm received: ID={alid}, Text={altx}, Code={alcd}")

        event_data = {
            'alid': alid,
            'altx': altx,
            'alcd': alcd,
            'timestamp': datetime.now().isoformat()
        }

        # Trigger generic alarm handler if registered (CEID -1 reserved for alarms)
        ALARM_EVENT_ID = -1
        if ALARM_EVENT_ID in self._event_handlers:
            for handler in self._event_handlers[ALARM_EVENT_ID]:
                asyncio.create_task(self._safe_run_handler(handler, event_data))

        # Send S5F2 reply with matching system_bytes
        if header.w_bit:
            await self._send_reply(header, 2, 0)  # ACKC5 = 0 (Accepted)

    async def _handle_event_report(self, header: HSMSHeader, data: Any):
        """Handle S6F11 (Event Report)"""
        if not isinstance(data, list) or len(data) < 3:
            logger.error("Invalid S6F11 format")
            return

        dataid = data[0]
        ceid = data[1]
        reports = data[2] if len(data) > 2 else []

        logger.info(f"Event report received: CEID={ceid}, DATAID={dataid}")

        self.stats['events_received'] += 1

        # Send S6F12 reply (CEACK = 0, accepted)
        if header.w_bit:
            await self._send_reply(header, 12, 0)

        # Call registered event handlers
        if ceid in self._event_handlers:
            event_data = {
                'dataid': dataid,
                'ceid': ceid,
                'reports': reports,
                'timestamp': datetime.now().isoformat()
            }

            loop = asyncio.get_running_loop()
            for handler in self._event_handlers[ceid]:
                try:
                    if asyncio.iscoroutinefunction(handler):
                        asyncio.create_task(self._safe_run_handler(handler, event_data))
                    else:
                        # Run sync handlers in executor to avoid blocking event loop
                        loop.run_in_executor(None, handler, event_data)
                except Exception as e:
                    logger.error(f"Error triggering event handler for CEID {ceid}: {e}")

    async def _safe_run_handler(self, handler, event_data):
        """Run an async handler and catch exceptions to avoid unhandled task errors"""
        try:
            await handler(event_data)
        except Exception as e:
            logger.error(f"Error in async event handler: {e}")

    # ------------------------------------------------------------------------
    # Status and Monitoring
    # ------------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        Get driver and connection status

        Returns:
            Status dictionary
        """
        return {
            'connected': self.connected,
            'selected': self.selected,
            'equipment': self.config.get_equipment_info(),
            'connection': {
                'host': self.config.connection.ip_address,
                'port': self.config.connection.port,
                'mode': self.config.connection.mode
            },
            'statistics': self.stats.copy(),
            'auto_reconnect': self._auto_reconnect
        }

    async def get_equipment_status(self, svids: Optional[List[int]] = None) -> Dict[int, Any]:
        """
        Get equipment status variables (S1F3/F4)

        Args:
            svids: List of SVIDs to request (None = all configured)

        Returns:
            Dictionary mapping SVID to value
        """
        if svids is None:
            # Get all configured SVIDs
            svids = list(self.config.data_variables.keys())

        # Send S1F3
        reply = await self.send("S1F3", {"SVID": svids})

        if not reply or 'SV' not in reply:
            return {}

        # Map SVIDs to values
        sv_values = reply['SV']
        return {svid: value for svid, value in zip(svids, sv_values)}

    # ------------------------------------------------------------------------
    # Configuration Management
    # ------------------------------------------------------------------------

    def switch_config(self, new_config_path: str):
        """
        Switch to a different equipment configuration

        Note: Must disconnect before switching and reconnect after.

        Args:
            new_config_path: Path to new configuration file

        Raises:
            RuntimeError: If currently connected
            ValueError: If new configuration is invalid
        """
        if self.connected:
            raise RuntimeError("Must disconnect before switching configuration")

        logger.info(f"Switching configuration to {new_config_path}")

        # Load new configuration
        new_config = self.config_loader.load(new_config_path)

        if not new_config.is_valid():
            raise ValueError(f"Invalid configuration: {new_config_path}")

        # Update configuration
        self.config_path = Path(new_config_path)
        self.config = new_config

        # Recreate message builder
        self.message_builder = MessageBuilder(self.config)

        # Recreate HSMS connection
        conn_params = self.config.get_connection_params()
        self.connection = HSMSConnection(**conn_params)
        self.connection.on_message_received = self._handle_message
        self.connection.on_connection_lost = self._handle_connection_lost

        logger.info(f"✅ Configuration switched to {self.config.equipment.type}")

    def reload_config(self):
        """Reload current configuration file (hot-reload)"""
        self.switch_config(str(self.config_path))

    # ------------------------------------------------------------------------
    # Utility Methods
    # ------------------------------------------------------------------------

    def _format_reply(self, decoded_data: Any) -> Dict[str, Any]:
        """Format decoded reply data as dictionary"""
        if isinstance(decoded_data, list):
            # Try to convert alternating key-value list to dict
            if len(decoded_data) % 2 == 0 and all(isinstance(decoded_data[i], str) for i in range(0, len(decoded_data), 2)):
                result = {}
                for i in range(0, len(decoded_data), 2):
                    result[decoded_data[i]] = decoded_data[i + 1]
                return result
            else:
                # Return as-is if not key-value format
                return {'data': decoded_data}
        else:
            return {'value': decoded_data}

    def __repr__(self):
        status = "connected" if self.connected else "disconnected"
        return f"SecsGemDriver({self.config.equipment.type}, {status})"


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    import sys
    from pathlib import Path

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    async def main():
        print("="*80)
        print("SecsGemDriver API Test")
        print("="*80)

        # Find config
        project_root = Path(__file__).parent.parent.parent
        config_path = str(project_root / "configs" / "amat_centura.yaml")

        try:
            # Create driver
            print(f"\n📦 Creating driver...")
            driver = SecsGemDriver(config_path)
            print(f"✅ Driver created: {driver}")

            # Get status
            print(f"\n📊 Driver Status:")
            status = driver.get_status()
            print(f"   Equipment: {status['equipment']['type']}")
            print(f"   Connected: {status['connected']}")
            print(f"   Auto-reconnect: {status['auto_reconnect']}")

            # Note: Actual connection would require real equipment
            print(f"\n⚠️  Skipping actual connection (no equipment available)")
            print(f"   In production, use:")
            print(f"     await driver.connect()")
            print(f"     response = await driver.send('S1F1')")
            print(f"     await driver.send_command('START', params)")
            print(f"     await driver.disconnect()")

        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()

    asyncio.run(main())
