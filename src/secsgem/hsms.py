"""
HSMS (High-Speed SECS Message Services) Protocol Implementation
================================================================

This module implements the HSMS protocol (SEMI E37) for SECS/GEM communication.
It handles:
- HSMS connection establishment (active/passive modes)
- Message header parsing and construction
- Control messages (Select, Deselect, Linktest, Separate)
- Data message transmission
- Heartbeat mechanism

Reference: SEMI E37 - High-Speed SECS Message Services (HSMS) Generic Services
"""

import asyncio
import inspect
import struct
import logging
from enum import IntEnum
from typing import Optional, Tuple, Callable, Dict, Any
from dataclasses import dataclass

# Configure logging
logger = logging.getLogger(__name__)


# ============================================================================
# HSMS Protocol Constants
# ============================================================================

class HSMSMessageType(IntEnum):
    """HSMS Message Types (Session Type field)"""
    DATA_MESSAGE = 0          # SECS-II data message
    SELECT_REQ = 1            # Select.req
    SELECT_RSP = 2            # Select.rsp
    DESELECT_REQ = 3          # Deselect.req
    DESELECT_RSP = 4          # Deselect.rsp
    LINKTEST_REQ = 5          # Linktest.req
    LINKTEST_RSP = 6          # Linktest.rsp
    REJECT_REQ = 7            # Reject.req
    SEPARATE_REQ = 9          # Separate.req


class HSMSSelectStatus(IntEnum):
    """Select Response Status Codes"""
    SUCCESS = 0               # Communication established successfully
    ALREADY_ACTIVE = 1        # Communication already active
    NOT_READY = 2             # Equipment not ready to communicate
    EXHAUSTED = 3             # Connection resources exhausted


class HSMSDeselectStatus(IntEnum):
    """Deselect Response Status Codes"""
    SUCCESS = 0               # Communication terminated successfully
    NOT_SELECTED = 1          # Communication not established
    BUSY = 2                  # Busy, cannot terminate now


class HSMSRejectReason(IntEnum):
    """Reject Request Reason Codes"""
    NOT_SUPPORTED = 1         # Message type not supported
    NOT_SELECTED = 2          # Not in selected state
    MESSAGE_TOO_LONG = 3      # Message length exceeds maximum
    ENTITY_TOO_LONG = 4       # Entity ID field too long


# ============================================================================
# HSMS Message Header Structure
# ============================================================================

@dataclass
class HSMSHeader:
    """
    HSMS Message Header (10 bytes)

    Structure:
    - Session ID (2 bytes): Identifies the communication session
    - Header Byte 2 (1 byte): Stream code (for data messages)
    - Header Byte 3 (1 byte): Function code (for data messages)
    - PType (1 byte): Presentation type (always 0 for SECS-II)
    - SType (1 byte): Session type (message type)
    - System Bytes (4 bytes): Transaction identifier
    """
    session_id: int          # 0-65535
    stream: int              # 0-127 (bit 7 is W-Bit)
    function: int            # 0-255
    p_type: int              # Presentation type (0 for SECS-II)
    s_type: int              # Session type (message type)
    system_bytes: int        # Transaction ID (0-4294967295)

    @property
    def w_bit(self) -> bool:
        """Extract W-Bit (Wait Bit) from stream byte"""
        return (self.stream & 0x80) != 0

    @w_bit.setter
    def w_bit(self, value: bool):
        """Set W-Bit in stream byte"""
        if value:
            self.stream |= 0x80
        else:
            self.stream &= 0x7F

    def to_bytes(self) -> bytes:
        """Encode header to 10-byte binary format"""
        return struct.pack(
            '>HBBBBI',
            self.session_id,
            self.stream,
            self.function,
            self.p_type,
            self.s_type,
            self.system_bytes
        )

    @classmethod
    def from_bytes(cls, data: bytes) -> 'HSMSHeader':
        """Decode header from 10-byte binary format"""
        if len(data) < 10:
            raise ValueError(f"HSMS header must be 10 bytes, got {len(data)}")

        session_id, stream, function, p_type, s_type, system_bytes = struct.unpack(
            '>HBBBBI', data[:10]
        )

        return cls(
            session_id=session_id,
            stream=stream,
            function=function,
            p_type=p_type,
            s_type=s_type,
            system_bytes=system_bytes
        )

    def __repr__(self) -> str:
        msg_type = HSMSMessageType(self.s_type).name if self.s_type in HSMSMessageType._value2member_map_ else f"Unknown({self.s_type})"
        if self.s_type == HSMSMessageType.DATA_MESSAGE:
            return f"HSMS<S{self.stream & 0x7F}F{self.function} W={self.w_bit} SYS={self.system_bytes}>"
        else:
            return f"HSMS<{msg_type} SYS={self.system_bytes}>"


# ============================================================================
# HSMS Connection Manager
# ============================================================================

class HSMSConnection:
    """
    HSMS Connection Manager

    Manages TCP connection and HSMS protocol state machine.
    Supports both Active (client) and Passive (server) modes.
    """

    def __init__(
        self,
        host: str,
        port: int,
        device_id: int = 0,
        session_id: int = 0,
        mode: str = 'active',
        connect_timeout: int = 30,
        reply_timeout: int = 10,
        t3_timeout: int = 120
    ):
        """
        Initialize HSMS connection

        Args:
            host: Equipment IP address
            port: HSMS port (typically 5000)
            device_id: Device ID for HSMS protocol
            session_id: Session ID for HSMS communication
            mode: 'active' (client) or 'passive' (server)
            connect_timeout: Connection timeout in seconds
            reply_timeout: Reply timeout for messages in seconds
            t3_timeout: Inter-character timeout in seconds
        """
        self.host = host
        self.port = port
        self.device_id = device_id
        self.session_id = session_id
        self.mode = mode.lower()
        self.connect_timeout = connect_timeout
        self.reply_timeout = reply_timeout
        self.t3_timeout = t3_timeout

        # Connection state
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self.connected = False
        self.selected = False
        self._server: Optional[asyncio.AbstractServer] = None
        self._passive_connected = asyncio.Event()

        # Max message length (default 10MB, per SEMI E37 practical limits)
        self.max_message_length = 10 * 1024 * 1024

        # Transaction tracking
        self._system_counter = 0
        self._pending_replies: Dict[int, asyncio.Future] = {}

        # Event handlers
        self.on_message_received: Optional[Callable] = None
        self.on_connection_lost: Optional[Callable] = None

        # Background tasks
        self._receive_task: Optional[asyncio.Task] = None
        self._heartbeat_task: Optional[asyncio.Task] = None

        logger.info(f"HSMS Connection initialized: {host}:{port} (mode={mode})")

    # ------------------------------------------------------------------------
    # Connection Management
    # ------------------------------------------------------------------------

    async def connect(self) -> bool:
        """
        Establish HSMS connection

        Returns:
            True if connection successful, False otherwise
        """
        try:
            if self.mode == 'active':
                logger.info(f"Connecting to {self.host}:{self.port} (active mode)...")
                self.reader, self.writer = await asyncio.wait_for(
                    asyncio.open_connection(self.host, self.port),
                    timeout=self.connect_timeout
                )
            else:
                logger.info(f"Listening on port {self.port} (passive mode)...")
                self._passive_connected.clear()
                self._server = await asyncio.start_server(
                    self._handle_client,
                    self.host,
                    self.port
                )
                # Wait for client connection with timeout
                try:
                    await asyncio.wait_for(
                        self._passive_connected.wait(),
                        timeout=self.connect_timeout
                    )
                except asyncio.TimeoutError:
                    logger.error(f"No client connected within {self.connect_timeout}s")
                    self._server.close()
                    await self._server.wait_closed()
                    self._server = None
                    return False

            self.connected = True
            logger.info(f"TCP connection established to {self.host}:{self.port}")

            # Start receive task
            self._receive_task = asyncio.create_task(self._receive_loop())

            # Send Select.req to establish HSMS session
            if await self.send_select():
                logger.info("HSMS session selected successfully")
                return True
            else:
                logger.error("HSMS session selection failed")
                await self.disconnect()
                return False

        except asyncio.TimeoutError:
            logger.error(f"Connection timeout after {self.connect_timeout}s")
            return False
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    async def disconnect(self, skip_deselect: bool = False):
        """Gracefully disconnect HSMS connection"""
        if not self.connected and not self._server:
            return

        try:
            # Send Deselect.req if selected (skip if peer already disconnected)
            if self.selected and not skip_deselect:
                try:
                    await self.send_deselect()
                except Exception:
                    pass

            # Cancel all pending reply futures
            pending = list(self._pending_replies.values())
            self._pending_replies.clear()
            for future in pending:
                if not future.done():
                    future.cancel()

            # Cancel background tasks
            if self._receive_task:
                self._receive_task.cancel()
            if self._heartbeat_task:
                self._heartbeat_task.cancel()

            # Close TCP connection
            if self.writer:
                self.writer.close()
                try:
                    await self.writer.wait_closed()
                except Exception:
                    pass

            # Close passive mode server
            if self._server:
                self._server.close()
                await self._server.wait_closed()
                self._server = None

            self.connected = False
            self.selected = False
            logger.info("HSMS connection closed")

        except Exception as e:
            logger.error(f"Error during disconnect: {e}")
            self.connected = False
            self.selected = False

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle incoming client connection (passive mode)"""
        if self.connected:
            peer = writer.get_extra_info('peername')
            logger.warning(f"Rejecting duplicate connection from {peer}")
            writer.close()
            await writer.wait_closed()
            return
        self.reader = reader
        self.writer = writer
        self.connected = True
        self._passive_connected.set()
        logger.info(f"Client connected from {writer.get_extra_info('peername')}")

    # ------------------------------------------------------------------------
    # HSMS Control Messages
    # ------------------------------------------------------------------------

    async def send_select(self) -> bool:
        """
        Send Select.req and wait for Select.rsp

        Returns:
            True if select successful, False otherwise
        """
        header = HSMSHeader(
            session_id=0xFFFF,
            stream=0,
            function=0,
            p_type=0,
            s_type=HSMSMessageType.SELECT_REQ,
            system_bytes=self._get_next_system_bytes()
        )

        logger.debug(f"Sending Select.req: {header}")

        try:
            response = await self._send_control_message(header)

            if response.s_type == HSMSMessageType.SELECT_RSP:
                status = response.function  # Status is in function byte
                if status == HSMSSelectStatus.SUCCESS:
                    self.selected = True
                    logger.info("Select.rsp received: SUCCESS")
                    return True
                else:
                    status_name = HSMSSelectStatus(status).name if status in HSMSSelectStatus._value2member_map_ else f"Unknown({status})"
                    logger.error(f"Select.rsp received: {status_name}")
                    return False
            else:
                logger.error(f"Unexpected response to Select.req: {response}")
                return False

        except asyncio.TimeoutError:
            logger.error("Select.req timeout")
            return False
        except Exception as e:
            logger.error(f"Select.req failed: {e}")
            return False

    async def send_deselect(self) -> bool:
        """
        Send Deselect.req and wait for Deselect.rsp

        Returns:
            True if deselect successful, False otherwise
        """
        header = HSMSHeader(
            session_id=0xFFFF,
            stream=0,
            function=0,
            p_type=0,
            s_type=HSMSMessageType.DESELECT_REQ,
            system_bytes=self._get_next_system_bytes()
        )

        logger.debug(f"Sending Deselect.req: {header}")

        try:
            response = await self._send_control_message(header)

            if response.s_type == HSMSMessageType.DESELECT_RSP:
                status = response.function
                if status == HSMSDeselectStatus.SUCCESS:
                    self.selected = False
                    logger.info("Deselect.rsp received: SUCCESS")
                    return True
                else:
                    status_name = HSMSDeselectStatus(status).name if status in HSMSDeselectStatus._value2member_map_ else f"Unknown({status})"
                    logger.error(f"Deselect.rsp received: {status_name}")
                    return False
            else:
                logger.error(f"Unexpected response to Deselect.req: {response}")
                return False

        except asyncio.TimeoutError:
            logger.error("Deselect.req timeout")
            return False
        except Exception as e:
            logger.error(f"Deselect.req failed: {e}")
            return False

    async def send_linktest(self) -> bool:
        """
        Send Linktest.req and wait for Linktest.rsp (heartbeat)

        Returns:
            True if linktest successful, False otherwise
        """
        header = HSMSHeader(
            session_id=0xFFFF,
            stream=0,
            function=0,
            p_type=0,
            s_type=HSMSMessageType.LINKTEST_REQ,
            system_bytes=self._get_next_system_bytes()
        )

        logger.debug(f"Sending Linktest.req: {header}")

        try:
            response = await self._send_control_message(header)

            if response.s_type == HSMSMessageType.LINKTEST_RSP:
                logger.debug("Linktest.rsp received")
                return True
            else:
                logger.error(f"Unexpected response to Linktest.req: {response}")
                return False

        except asyncio.TimeoutError:
            logger.warning("Linktest.req timeout")
            return False
        except Exception as e:
            logger.error(f"Linktest.req failed: {e}")
            return False

    # ------------------------------------------------------------------------
    # Data Message Transmission
    # ------------------------------------------------------------------------

    async def send_data_message(
        self,
        stream: int,
        function: int,
        wait_bit: bool,
        data: bytes = b''
    ) -> Optional[Tuple[HSMSHeader, bytes]]:
        """
        Send SECS-II data message

        Args:
            stream: Stream number (0-127)
            function: Function number (0-255)
            wait_bit: True if expecting reply
            data: SECS-II encoded message body

        Returns:
            (header, data) tuple if wait_bit=True, None otherwise
        """
        if not self.selected:
            raise RuntimeError("HSMS session not selected")

        header = HSMSHeader(
            session_id=self.session_id,
            stream=stream,
            function=function,
            p_type=0,
            s_type=HSMSMessageType.DATA_MESSAGE,
            system_bytes=self._get_next_system_bytes()
        )
        header.w_bit = wait_bit

        logger.debug(f"Sending data message: {header}, data length={len(data)}")

        if wait_bit:
            # Register future BEFORE sending to avoid race condition
            # where reply arrives before future is registered
            future: asyncio.Future = asyncio.Future()
            self._pending_replies[header.system_bytes] = future

            try:
                await self._send_message(header, data)
                result = await asyncio.wait_for(future, timeout=self.reply_timeout)
                reply_header, reply_data = result
                logger.debug(f"Received reply: {reply_header}, data length={len(reply_data)}")
                return (reply_header, reply_data)
            except asyncio.TimeoutError:
                logger.error(f"Reply timeout for {header}")
                raise
            finally:
                self._pending_replies.pop(header.system_bytes, None)
        else:
            await self._send_message(header, data)
            return None

    # ------------------------------------------------------------------------
    # Internal Methods
    # ------------------------------------------------------------------------

    def _get_next_system_bytes(self) -> int:
        """Generate next system bytes (transaction ID)"""
        self._system_counter = (self._system_counter + 1) % 0x100000000
        return self._system_counter

    async def _send_message(self, header: HSMSHeader, data: bytes = b''):
        """Send HSMS message (header + data)"""
        if not self.writer:
            raise RuntimeError("Not connected")

        # Message length (10-byte header + data)
        message_length = 10 + len(data)

        # Construct complete message: [4-byte length][10-byte header][data]
        message = struct.pack('>I', message_length) + header.to_bytes() + data

        self.writer.write(message)
        await self.writer.drain()

    async def _send_control_message(self, header: HSMSHeader) -> HSMSHeader:
        """Send control message and wait for response"""
        system_bytes = header.system_bytes

        # Create future for reply
        future = asyncio.Future()
        self._pending_replies[system_bytes] = future

        try:
            # Send message
            await self._send_message(header)

            # Wait for reply
            reply_header = await asyncio.wait_for(future, timeout=self.reply_timeout)
            return reply_header

        finally:
            # Clean up
            if system_bytes in self._pending_replies:
                del self._pending_replies[system_bytes]

    async def send_reply(self, original_header: HSMSHeader, reply_stream: int,
                         reply_function: int, data: bytes = b''):
        """Send a reply message matching the system_bytes of the original message"""
        header = HSMSHeader(
            session_id=self.session_id,
            stream=reply_stream,
            function=reply_function,
            p_type=0,
            s_type=HSMSMessageType.DATA_MESSAGE,
            system_bytes=original_header.system_bytes
        )
        await self._send_message(header, data)

    async def _invoke_callback(self, callback: Optional[Callable], *args):
        """Safely invoke a callback, handling both sync and async callables"""
        if callback is None:
            return
        if inspect.iscoroutinefunction(callback):
            await callback(*args)
        else:
            callback(*args)

    async def _receive_loop(self):
        """Background task to receive and process incoming messages"""
        logger.info("Receive loop started")

        try:
            while self.connected and self.reader:
                # Read message length (4 bytes)
                length_bytes = await self.reader.readexactly(4)
                message_length = struct.unpack('>I', length_bytes)[0]

                # Validate message length to prevent DoS
                if message_length < 10:
                    logger.error(f"Invalid message length {message_length} (minimum 10)")
                    break
                if message_length > self.max_message_length:
                    logger.error(
                        f"Message length {message_length} exceeds limit "
                        f"{self.max_message_length}, dropping connection"
                    )
                    break

                # Read complete message
                message_data = await self.reader.readexactly(message_length)

                # Parse header
                header = HSMSHeader.from_bytes(message_data[:10])
                data = message_data[10:] if len(message_data) > 10 else b''

                logger.debug(f"Received message: {header}, data length={len(data)}")

                # Handle message
                await self._handle_received_message(header, data)

        except asyncio.CancelledError:
            logger.info("Receive loop cancelled")
            return
        except asyncio.IncompleteReadError:
            logger.error("Connection closed by peer")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")

        # Connection broken or invalid data received - clean up
        self.connected = False
        await self._invoke_callback(self.on_connection_lost)

    async def _handle_received_message(self, header: HSMSHeader, data: bytes):
        """Process received message"""

        # Check if this is a reply to a pending request
        if header.system_bytes in self._pending_replies:
            future = self._pending_replies[header.system_bytes]
            if not future.done():
                if header.s_type == HSMSMessageType.DATA_MESSAGE:
                    future.set_result((header, data))
                else:
                    future.set_result(header)
            return

        # Handle control messages
        if header.s_type == HSMSMessageType.SELECT_REQ:
            await self._handle_select_req(header)
        elif header.s_type == HSMSMessageType.DESELECT_REQ:
            await self._handle_deselect_req(header)
        elif header.s_type == HSMSMessageType.LINKTEST_REQ:
            await self._handle_linktest_req(header)
        elif header.s_type == HSMSMessageType.SEPARATE_REQ:
            await self._handle_separate_req(header)
        elif header.s_type == HSMSMessageType.DATA_MESSAGE:
            # Primary message (not a reply)
            await self._invoke_callback(self.on_message_received, header, data)
        else:
            logger.warning(f"Unhandled message type: {header}")

    async def _handle_select_req(self, header: HSMSHeader):
        """Handle incoming Select.req"""
        logger.info("Received Select.req")

        # Send Select.rsp with SUCCESS
        response = HSMSHeader(
            session_id=header.session_id,
            stream=0,
            function=HSMSSelectStatus.SUCCESS,
            p_type=0,
            s_type=HSMSMessageType.SELECT_RSP,
            system_bytes=header.system_bytes
        )

        await self._send_message(response)
        self.selected = True
        logger.info("Sent Select.rsp: SUCCESS")

    async def _handle_deselect_req(self, header: HSMSHeader):
        """Handle incoming Deselect.req"""
        logger.info("Received Deselect.req")

        # Send Deselect.rsp with SUCCESS
        response = HSMSHeader(
            session_id=header.session_id,
            stream=0,
            function=HSMSDeselectStatus.SUCCESS,
            p_type=0,
            s_type=HSMSMessageType.DESELECT_RSP,
            system_bytes=header.system_bytes
        )

        await self._send_message(response)
        self.selected = False
        logger.info("Sent Deselect.rsp: SUCCESS")

    async def _handle_linktest_req(self, header: HSMSHeader):
        """Handle incoming Linktest.req"""
        logger.debug("Received Linktest.req")

        # Send Linktest.rsp
        response = HSMSHeader(
            session_id=header.session_id,
            stream=0,
            function=0,
            p_type=0,
            s_type=HSMSMessageType.LINKTEST_RSP,
            system_bytes=header.system_bytes
        )

        await self._send_message(response)
        logger.debug("Sent Linktest.rsp")

    async def _handle_separate_req(self, header: HSMSHeader):
        """Handle incoming Separate.req (no response per SEMI E37)"""
        logger.warning("Received Separate.req - closing connection")
        await self.disconnect(skip_deselect=True)

    # ------------------------------------------------------------------------
    # Heartbeat
    # ------------------------------------------------------------------------

    async def start_heartbeat(self, interval: int = 60):
        """
        Start heartbeat task (periodic Linktest)

        Args:
            interval: Heartbeat interval in seconds
        """
        async def heartbeat_loop():
            try:
                while self.selected:
                    await asyncio.sleep(interval)
                    try:
                        if not await self.send_linktest():
                            logger.error("Heartbeat failed - connection may be lost")
                            await self._invoke_callback(self.on_connection_lost)
                            break
                    except asyncio.CancelledError:
                        raise
                    except Exception as e:
                        logger.error(f"Heartbeat error: {e}")
                        break
            except asyncio.CancelledError:
                logger.debug("Heartbeat loop cancelled")

        self._heartbeat_task = asyncio.create_task(heartbeat_loop())
        logger.info(f"Heartbeat started with {interval}s interval")


# ============================================================================
# Example Usage
# ============================================================================

async def main():
    """Example usage of HSMS protocol"""
    import os

    # 从环境变量读取连接参数，或使用占位符
    host = os.environ.get("HSMS_HOST", "192.168.1.100")  # 必须配置实际设备 IP
    port = int(os.environ.get("HSMS_PORT", "5000"))      # 必须配置实际设备端口

    # Create connection
    connection = HSMSConnection(
        host=host,
        port=port,
        device_id=0,
        session_id=0,
        mode='active'
    )

    # Set up message handler
    async def on_message(header: HSMSHeader, data: bytes):
        print(f"Received message: {header}")
        print(f"Data: {data.hex()}")

    connection.on_message_received = on_message

    # Connect
    if await connection.connect():
        print("Connected successfully")

        # Start heartbeat
        await connection.start_heartbeat(interval=60)

        # Send a test message (S1F1 - Are You There)
        try:
            reply = await connection.send_data_message(
                stream=1,
                function=1,
                wait_bit=True,
                data=b''
            )
            if reply:
                print(f"Received reply: {reply[0]}")
        except Exception as e:
            print(f"Error sending message: {e}")

        # Keep connection alive for testing
        await asyncio.sleep(10)

        # Disconnect
        await connection.disconnect()
    else:
        print("Connection failed")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
