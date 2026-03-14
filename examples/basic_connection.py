#!/usr/bin/env python3
"""
Basic Connection Example
========================

This example demonstrates how to:
1. Connect to semiconductor equipment using HSMS
2. Send basic SECS messages (S1F1/F2 - Are You There)
3. Handle incoming messages
4. Maintain connection with heartbeat
5. Gracefully disconnect

Usage:
    python examples/basic_connection.py
"""

import asyncio
import sys
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from secsgem.hsms import HSMSConnection, HSMSHeader


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Main connection example"""

    # ========================================================================
    # 1. Configure Connection Parameters
    # ========================================================================

    # AMAT Centura example (modify for your equipment)
    EQUIPMENT_IP = "192.168.10.101"
    EQUIPMENT_PORT = 5000
    DEVICE_ID = 0
    SESSION_ID = 0

    logger.info("="*80)
    logger.info("Universal SECS/GEM Driver - Basic Connection Example")
    logger.info("="*80)

    # ========================================================================
    # 2. Create HSMS Connection
    # ========================================================================

    connection = HSMSConnection(
        host=EQUIPMENT_IP,
        port=EQUIPMENT_PORT,
        device_id=DEVICE_ID,
        session_id=SESSION_ID,
        mode='active',              # Driver initiates connection
        connect_timeout=30,         # 30 second connection timeout
        reply_timeout=10,           # 10 second reply timeout
        t3_timeout=120              # 2 minute inter-character timeout
    )

    # ========================================================================
    # 3. Set Up Message Handler
    # ========================================================================

    async def on_message_received(header: HSMSHeader, data: bytes):
        """
        Callback for incoming SECS messages from equipment

        This handler is called for:
        - Primary messages (not replies)
        - Event reports (S6F11)
        - Alarms
        - Status changes
        """
        logger.info(f"📨 Received message from equipment: {header}")
        logger.info(f"   Data length: {len(data)} bytes")

        # Parse message based on stream/function
        if header.stream == 6 and header.function == 11:
            logger.info("   → Event Report (S6F11)")
            # TODO: Parse event data when SECS-II codec is implemented
        elif header.stream == 5 and header.function in [1, 3, 5, 7, 9, 11]:
            logger.info("   → Alarm message")
        else:
            logger.info(f"   → S{header.stream}F{header.function}")

        if data:
            logger.debug(f"   Data (hex): {data.hex()}")

    connection.on_message_received = on_message_received

    # ========================================================================
    # 4. Set Up Connection Lost Handler
    # ========================================================================

    async def on_connection_lost():
        """Callback when connection is lost"""
        logger.error("❌ Connection lost to equipment!")
        # TODO: Implement auto-reconnect logic here

    connection.on_connection_lost = on_connection_lost

    # ========================================================================
    # 5. Connect to Equipment
    # ========================================================================

    logger.info(f"Connecting to {EQUIPMENT_IP}:{EQUIPMENT_PORT}...")

    if not await connection.connect():
        logger.error("❌ Failed to connect to equipment")
        return

    logger.info("✅ Connected to equipment successfully")
    logger.info("✅ HSMS session selected")

    # ========================================================================
    # 6. Start Heartbeat
    # ========================================================================

    logger.info("Starting heartbeat mechanism...")
    await connection.start_heartbeat(interval=60)  # Send linktest every 60 seconds
    logger.info("✅ Heartbeat started (60s interval)")

    # ========================================================================
    # 7. Send S1F1 - Are You There Request
    # ========================================================================

    try:
        logger.info("\nSending S1F1 (Are You There) to equipment...")

        reply_header, reply_data = await connection.send_data_message(
            stream=1,
            function=1,
            wait_bit=True,      # Expect reply (S1F2)
            data=b''            # No data for S1F1
        )

        logger.info(f"✅ Received S1F2 reply: {reply_header}")
        logger.info(f"   Data length: {len(reply_data)} bytes")

        # Parse S1F2 response (Model Name and Software Revision)
        # TODO: Proper parsing when SECS-II codec is implemented
        if reply_data:
            logger.info(f"   Equipment info (raw): {reply_data.hex()}")

    except asyncio.TimeoutError:
        logger.error("❌ S1F1 timeout - equipment not responding")
    except Exception as e:
        logger.error(f"❌ Error sending S1F1: {e}")

    # ========================================================================
    # 8. Keep Connection Alive
    # ========================================================================

    logger.info("\n" + "="*80)
    logger.info("Connection established and monitoring equipment")
    logger.info("Press Ctrl+C to disconnect")
    logger.info("="*80 + "\n")

    try:
        # Keep connection alive - in production, this would be your main loop
        # where you handle equipment control, data collection, etc.
        await asyncio.sleep(300)  # Run for 5 minutes

    except KeyboardInterrupt:
        logger.info("\n⚠️  Ctrl+C detected - initiating graceful shutdown...")

    # ========================================================================
    # 9. Disconnect
    # ========================================================================

    logger.info("Disconnecting from equipment...")
    await connection.disconnect()
    logger.info("✅ Disconnected successfully")

    logger.info("\n" + "="*80)
    logger.info("Example completed")
    logger.info("="*80)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
