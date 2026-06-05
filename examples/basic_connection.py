"""Basic HSMS connection skeleton.

This is an evaluation example only. Replace the host, port, and message map with
your validated equipment-specific configuration before any production use.
"""

import asyncio
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from secsgem import SecsGemDriver  # noqa: E402


async def main():
    driver = SecsGemDriver("configs/generic_legacy_serial_gateway.yaml")
    print("Loaded generic config for:", driver.config.equipment.type)
    print("This example does not auto-connect. Configure a real host path first.")


if __name__ == "__main__":
    asyncio.run(main())
