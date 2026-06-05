"""Configuration loading example for the generic legacy gateway config."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from secsgem import ConfigLoader  # noqa: E402


config = ConfigLoader().load("configs/generic_legacy_serial_gateway.yaml")
print(config.get_equipment_info())
print("messages:", sorted(config.messages))
print("data variables:", sorted(config.data_variables))
