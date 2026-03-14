#!/usr/bin/env python3
"""
Configuration-Driven Example
=============================

Demonstrates how to use the SecsGemDriver with YAML configuration files
for equipment communication without hardcoding any message definitions.

Usage:
    python examples/config_driven.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from secsgem import SecsGemDriver


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    # Load equipment configuration from YAML
    config_path = str(Path(__file__).parent.parent / "configs" / "amat_centura.yaml")

    logger.info("Creating driver from configuration...")
    driver = SecsGemDriver(config_path)

    # Print driver status (no connection needed)
    status = driver.get_status()
    logger.info(f"Equipment: {status['equipment']['type']}")
    logger.info(f"Vendor: {status['equipment']['vendor']}")
    logger.info(f"Connection target: {status['connection']['host']}:{status['connection']['port']}")

    # Register event handlers before connecting
    @driver.on_event(100)  # PROCESS_START
    async def on_process_start(event_data):
        logger.info(f"Process started: CEID={event_data['ceid']}")

    @driver.on_event(101)  # PROCESS_COMPLETE
    async def on_process_complete(event_data):
        logger.info(f"Process completed: {event_data}")

    @driver.on_event(-1)  # Alarm handler
    async def on_alarm(event_data):
        logger.warning(f"ALARM: ID={event_data['alid']}, Text={event_data['altx']}")

    logger.info("Event handlers registered")

    # In production, you would connect to real equipment:
    #
    #   await driver.connect()
    #   response = await driver.send("S1F1")
    #   await driver.send_command("START_DEPOSITION", {
    #       "RECIPE_ID": "ALU_SPUTTER_001",
    #       "LOT_ID": "LOT-2025-001",
    #       "WAFER_ID": "WAFER-001",
    #   })
    #   await driver.disconnect()

    logger.info("Configuration-driven example completed")


if __name__ == "__main__":
    asyncio.run(main())
