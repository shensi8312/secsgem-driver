"""Legacy equipment -> SECS/GEM bridge demo components.

These modules are intentionally small, local-only examples. They are not a
production-certified gateway and do not claim GEM compliance.
"""

from .gem_mapping import DemoGateway, DemoScenarioResult, StatusSnapshot
from .serial_adapter import LegacyAsciiAdapter

__all__ = [
    "DemoGateway",
    "DemoScenarioResult",
    "LegacyAsciiAdapter",
    "StatusSnapshot",
]
