"""
Configuration Loader
====================

This module handles loading and validation of YAML equipment configuration files.
It provides configuration management, validation, and access methods.

Features:
    - Load YAML configuration files
    - Validate configuration completeness and correctness
    - Provide typed access to configuration values
    - Support configuration hot-reloading
    - Cache configurations for performance

Usage:
    loader = ConfigLoader()
    config = loader.load("configs/amat_centura.yaml")

    if config.is_valid():
        conn_params = config.get_connection_params()
        driver = HSMSConnection(**conn_params)
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, field_validator


logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models for Configuration Validation
# ============================================================================

class EquipmentConfig(BaseModel):
    """Equipment identification configuration"""
    id: str = Field(..., description="Equipment identifier")
    type: str = Field(..., description="Equipment type")
    description: str = Field(..., description="Equipment description")
    location: str = Field(..., description="Equipment location")
    vendor: str = Field(..., description="Vendor name")


class ConnectionConfig(BaseModel):
    """HSMS connection configuration"""
    mode: str = Field(..., description="Connection mode (active/passive)")
    ip_address: str = Field(..., description="Equipment IP address")
    port: int = Field(..., ge=1, le=65535, description="HSMS port")
    connect_timeout: int = Field(default=30, ge=1, description="Connection timeout (seconds)")
    reply_timeout: int = Field(default=10, ge=1, description="Reply timeout (seconds)")
    t3_timeout: int = Field(default=120, ge=1, description="T3 timeout (seconds)")
    t5_timeout: int = Field(default=10, ge=1, description="T5 timeout (seconds)")
    t6_timeout: int = Field(default=5, ge=1, description="T6 timeout (seconds)")
    t7_timeout: int = Field(default=10, ge=1, description="T7 timeout (seconds)")
    t8_timeout: int = Field(default=5, ge=1, description="T8 timeout (seconds)")
    device_id: int = Field(default=0, ge=0, description="Device ID")
    session_id: int = Field(default=0, ge=0, description="Session ID")

    @field_validator('mode')
    @classmethod
    def validate_mode(cls, v):
        if v.lower() not in ['active', 'passive']:
            raise ValueError("mode must be 'active' or 'passive'")
        return v.lower()


class MessageStructureItem(BaseModel):
    """SECS message structure item definition"""
    name: str
    type: str
    description: str
    max_length: Optional[int] = None
    length: Optional[int] = None


class MessageDefinition(BaseModel):
    """SECS message definition"""
    stream: int = Field(..., ge=0, le=127, description="Stream number")
    function: int = Field(..., ge=0, le=255, description="Function number")
    wait_bit: bool = Field(..., description="Wait for reply")
    description: str = Field(..., description="Message description")
    structure: Optional[List[MessageStructureItem]] = Field(default=None, description="Message structure")


class DataVariableConfig(BaseModel):
    """Data variable (status variable) configuration"""
    name: str
    type: str
    description: str
    unit: str
    min: Optional[float] = None
    max: Optional[float] = None
    values: Optional[Dict[int, str]] = None  # For enum types


class CollectionEventConfig(BaseModel):
    """Collection event configuration"""
    name: str
    description: str
    associated_reports: List[int]


class ReportConfig(BaseModel):
    """Report configuration"""
    name: str
    description: str
    variables: List[int]


class CommandParameterConfig(BaseModel):
    """Command parameter configuration"""
    name: str
    type: str
    required: bool


class CommandConfig(BaseModel):
    """Remote command configuration"""
    description: str
    parameters: List[CommandParameterConfig] = Field(default_factory=list)


class SettingsConfig(BaseModel):
    """Driver behavior settings"""
    auto_reconnect: bool = Field(default=True)
    reconnect_interval: int = Field(default=30, ge=1)
    max_reconnect_attempts: int = Field(default=0, ge=0)
    heartbeat_enabled: bool = Field(default=True)
    heartbeat_interval: int = Field(default=60, ge=1)
    message_logging: bool = Field(default=True)
    log_file: str = Field(default="logs/equipment.log")
    log_level: str = Field(default="INFO")
    secs_trace: bool = Field(default=True)

    @field_validator('log_level')
    @classmethod
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"log_level must be one of {valid_levels}")
        return v.upper()


class AdvancedConfig(BaseModel):
    """Advanced driver settings"""
    max_queue_size: int = Field(default=1000, ge=1)
    message_cache_enabled: bool = Field(default=True)
    message_cache_ttl: int = Field(default=300, ge=0)
    metrics_enabled: bool = Field(default=True)
    metrics_interval: int = Field(default=60, ge=1)


# ============================================================================
# Main Configuration Class
# ============================================================================

@dataclass
class EquipmentConfiguration:
    """
    Complete equipment configuration

    This class wraps all configuration sections and provides convenient
    access methods for driver initialization.
    """

    # Configuration file path
    config_path: Path

    # Configuration sections
    equipment: EquipmentConfig
    connection: ConnectionConfig
    messages: Dict[str, MessageDefinition]
    data_variables: Dict[int, DataVariableConfig]
    collection_events: Dict[int, CollectionEventConfig]
    reports: Dict[int, ReportConfig]
    commands: Dict[str, CommandConfig]
    settings: SettingsConfig
    advanced: AdvancedConfig

    # Raw configuration data (for advanced usage)
    raw_config: Dict[str, Any] = field(default_factory=dict)

    def is_valid(self) -> bool:
        """Check if configuration is valid"""
        try:
            # Basic validation
            if not self.equipment or not self.connection:
                return False

            # Ensure essential messages are defined
            essential_messages = ['S1F1', 'S1F2', 'S1F13', 'S1F14']
            for msg in essential_messages:
                if msg not in self.messages:
                    logger.warning(f"Essential message {msg} not defined")
                    return False

            return True

        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False

    def get_connection_params(self) -> Dict[str, Any]:
        """
        Get connection parameters for HSMSConnection

        Returns:
            Dictionary of connection parameters
        """
        return {
            'host': self.connection.ip_address,
            'port': self.connection.port,
            'device_id': self.connection.device_id,
            'session_id': self.connection.session_id,
            'mode': self.connection.mode,
            'connect_timeout': self.connection.connect_timeout,
            'reply_timeout': self.connection.reply_timeout,
            't3_timeout': self.connection.t3_timeout
        }

    def get_message_definition(self, message_name: str) -> Optional[MessageDefinition]:
        """Get message definition by name (e.g., 'S1F1')"""
        return self.messages.get(message_name)

    def get_data_variable(self, svid: int) -> Optional[DataVariableConfig]:
        """Get data variable definition by SVID"""
        return self.data_variables.get(svid)

    def get_collection_event(self, ceid: int) -> Optional[CollectionEventConfig]:
        """Get collection event definition by CEID"""
        return self.collection_events.get(ceid)

    def get_report(self, rptid: int) -> Optional[ReportConfig]:
        """Get report definition by Report ID"""
        return self.reports.get(rptid)

    def get_command(self, command_name: str) -> Optional[CommandConfig]:
        """Get remote command definition"""
        return self.commands.get(command_name)

    def get_equipment_info(self) -> Dict[str, str]:
        """Get equipment information as dictionary"""
        return {
            'id': self.equipment.id,
            'type': self.equipment.type,
            'description': self.equipment.description,
            'location': self.equipment.location,
            'vendor': self.equipment.vendor
        }

    def __repr__(self):
        return (f"EquipmentConfiguration(equipment={self.equipment.type}, "
                f"location={self.equipment.location}, "
                f"messages={len(self.messages)}, "
                f"data_vars={len(self.data_variables)})")


# ============================================================================
# Configuration Loader
# ============================================================================

class ConfigLoader:
    """
    Configuration Loader and Manager

    Handles loading, parsing, and validating YAML configuration files.
    Provides caching and hot-reload capabilities.
    """

    def __init__(self):
        """Initialize configuration loader"""
        self._cache: Dict[str, EquipmentConfiguration] = {}
        logger.info("ConfigLoader initialized")

    def load(self, config_path: str) -> EquipmentConfiguration:
        """
        Load equipment configuration from YAML file

        Args:
            config_path: Path to YAML configuration file

        Returns:
            EquipmentConfiguration instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            yaml.YAMLError: If YAML parsing fails
            ValueError: If configuration validation fails
        """
        path = Path(config_path)

        # Check if file exists
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        logger.info(f"Loading configuration from {config_path}")

        # Load YAML
        with open(path, 'r', encoding='utf-8') as f:
            raw_config = yaml.safe_load(f)

        if not raw_config:
            raise ValueError(f"Empty configuration file: {config_path}")

        # Parse and validate
        config = self._parse_config(path, raw_config)

        # Cache configuration (use resolved path for consistency)
        self._cache[str(path.resolve())] = config

        logger.info(f"Configuration loaded successfully: {config.equipment.type}")

        return config

    def _parse_config(self, path: Path, raw_config: Dict[str, Any]) -> EquipmentConfiguration:
        """Parse raw YAML config into EquipmentConfiguration"""

        try:
            # Parse equipment section
            equipment = EquipmentConfig(**raw_config.get('equipment', {}))

            # Parse connection section
            connection = ConnectionConfig(**raw_config.get('connection', {}))

            # Parse messages (copy to avoid mutating raw_config)
            messages = {}
            for msg_name, msg_data in raw_config.get('messages', {}).items():
                msg_data = dict(msg_data)
                structure = msg_data.get('structure')
                if structure:
                    msg_data['structure'] = [
                        MessageStructureItem(**item) if isinstance(item, dict) else item
                        for item in structure
                    ]
                messages[msg_name] = MessageDefinition(**msg_data)

            # Parse data variables
            data_variables = {}
            for svid_str, var_data in raw_config.get('data_variables', {}).items():
                svid = int(svid_str)
                data_variables[svid] = DataVariableConfig(**var_data)

            # Parse collection events
            collection_events = {}
            for ceid_str, event_data in raw_config.get('collection_events', {}).items():
                ceid = int(ceid_str)
                collection_events[ceid] = CollectionEventConfig(**event_data)

            # Parse reports
            reports = {}
            for rptid_str, report_data in raw_config.get('reports', {}).items():
                rptid = int(rptid_str)
                reports[rptid] = ReportConfig(**report_data)

            # Parse commands
            commands = {}
            for cmd_name, cmd_data in raw_config.get('commands', {}).items():
                cmd_data = dict(cmd_data)
                params = cmd_data.get('parameters', [])
                cmd_data['parameters'] = [
                    CommandParameterConfig(**p) if isinstance(p, dict) else p
                    for p in params
                ]
                commands[cmd_name] = CommandConfig(**cmd_data)

            # Parse settings
            settings = SettingsConfig(**raw_config.get('settings', {}))

            # Parse advanced settings
            advanced = AdvancedConfig(**raw_config.get('advanced', {}))

            # Create configuration object
            config = EquipmentConfiguration(
                config_path=path,
                equipment=equipment,
                connection=connection,
                messages=messages,
                data_variables=data_variables,
                collection_events=collection_events,
                reports=reports,
                commands=commands,
                settings=settings,
                advanced=advanced,
                raw_config=raw_config
            )

            # Validate
            if not config.is_valid():
                raise ValueError("Configuration validation failed")

            return config

        except Exception as e:
            logger.error(f"Failed to parse configuration: {e}")
            raise ValueError(f"Configuration parsing error: {e}") from e

    def reload(self, config_path: str) -> EquipmentConfiguration:
        """
        Reload configuration from file (hot-reload)

        Args:
            config_path: Path to configuration file

        Returns:
            Updated EquipmentConfiguration
        """
        logger.info(f"Reloading configuration: {config_path}")

        # Remove from cache (normalize path to match load() cache key)
        cache_key = str(Path(config_path).resolve())
        if cache_key in self._cache:
            del self._cache[cache_key]

        # Load fresh configuration
        return self.load(config_path)

    def get_cached(self, config_path: str) -> Optional[EquipmentConfiguration]:
        """Get cached configuration if available"""
        return self._cache.get(config_path)

    def clear_cache(self):
        """Clear all cached configurations"""
        self._cache.clear()
        logger.info("Configuration cache cleared")

    def list_available_configs(self, config_dir: str = "configs") -> List[str]:
        """
        List all available configuration files

        Args:
            config_dir: Directory to search for configs

        Returns:
            List of config file paths
        """
        config_path = Path(config_dir)
        if not config_path.exists():
            return []

        configs = list(config_path.glob("*.yaml"))
        configs.extend(config_path.glob("*.yml"))

        return [str(c) for c in configs if c.name != 'template.yaml']


# ============================================================================
# Utility Functions
# ============================================================================

def validate_config_file(config_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate a configuration file without loading it fully

    Args:
        config_path: Path to configuration file

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        loader = ConfigLoader()
        config = loader.load(config_path)
        if config.is_valid():
            return True, None
        else:
            return False, "Configuration validation failed"
    except Exception as e:
        return False, str(e)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("="*80)
    print("Configuration Loader Test")
    print("="*80)

    # Create loader
    loader = ConfigLoader()

    # Find project root (assuming this script is in src/config/)
    project_root = Path(__file__).parent.parent.parent

    # List available configs
    print("\n📋 Available Configurations:")
    configs = loader.list_available_configs(str(project_root / "configs"))
    for i, config_file in enumerate(configs, 1):
        print(f"   {i}. {config_file}")

    # Load each config
    for config_file in configs:
        print(f"\n{'='*80}")
        print(f"Loading: {config_file}")
        print('='*80)

        try:
            config = loader.load(config_file)

            print(f"\n✅ Configuration loaded successfully")
            print(f"\n📦 Equipment Information:")
            for key, value in config.get_equipment_info().items():
                print(f"   {key}: {value}")

            print(f"\n🔌 Connection Parameters:")
            conn_params = config.get_connection_params()
            for key, value in conn_params.items():
                print(f"   {key}: {value}")

            print(f"\n📨 Message Definitions: {len(config.messages)}")
            print(f"📊 Data Variables: {len(config.data_variables)}")
            print(f"📢 Collection Events: {len(config.collection_events)}")
            print(f"📝 Reports: {len(config.reports)}")
            print(f"⚙️  Commands: {len(config.commands)}")

        except Exception as e:
            print(f"\n❌ Error loading configuration: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*80)
    print("✅ Configuration loader test completed")
    print("="*80)
