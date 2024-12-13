"""
FullAutomationClimate - Automated Climate Control for Home Assistant
==================================================================

This module provides automated climate control functionality for Home Assistant,
integrating with various sensors and conditions to optimize heating/cooling.

Features:
---------
- Automatic temperature control based on room occupancy
- Window/door opening detection and response
- External temperature monitoring and limits
- Weather forecast integration
- Support for multiple climate units
- Configurable delays and temperature setpoints
- Support for both climate entities and generic on/off devices

Requirements:
------------
- Home Assistant with AppDaemon
- Compatible climate devices
- Optional: occupancy sensors, door/window sensors, temperature sensors

Configuration:
-------------
Example configuration in apps.yaml:
```yaml
climate_automation:
  module: FullAutomationClimate
  class: FullAutomationClimate
  debug: false  # Optional: Enable debug logging
  climates:
    - climate_entity: climate.living_room
      occupancy_entity: binary_sensor.living_room_occupancy
      opening_entity: binary_sensor.living_room_window
      external_temperature_entity: sensor.outdoor_temperature
      heating_limit: 19
      to_occupied_delay: 10  # Optional: Delay in seconds
      to_inoccupied_delay: 10  # Optional: Delay in seconds
      opening_delay_open: 300  # Optional: Delay in seconds
      opening_delay_close: 15  # Optional: Delay in seconds
      occupied_heating_setpoint: 21  # Optional: Temperature in °C
      away_heating_setpoint: 17  # Optional: Temperature in °C
      off_heating_setpoint: 7  # Optional: Temperature in °C
```

Technical Details:
-----------------
The module implements a hierarchical configuration system:
1. Local entity values take precedence
2. Local fixed values are used if no entity exists
3. Global values are used as fallback
4. Default constants are used if no other values are available

The system supports:
- Multiple climate units with independent configurations
- Automatic mode switching based on occupancy
- Temperature adjustments based on external conditions
- Configurable delays to prevent rapid switching
- Extensive error handling and logging

Error Handling:
--------------
- All entity interactions are wrapped in try-except blocks
- Invalid configurations are logged with detailed error messages
- Missing entities are gracefully handled with fallback values
- Temperature conversion errors are caught and logged

Author: @gnol86
License: MIT
Repository: https://github.com/Gnol86/FullAutomationClimate
"""

import appdaemon.plugins.hass.hassapi as hass # type: ignore
import traceback
from typing import Optional, Dict, List, Any, Union, TypedDict
from enum import Enum, auto

class EntityState(Enum):
    """
    Enumeration of possible entity states in Home Assistant.
    
    This enum defines the standard states that can be returned by Home Assistant entities,
    ensuring consistent state handling across the application.
    """
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    ON = "on"
    OFF = "off"
    HOME = "home"
    TRUE = "true"
    TRUE_BOOL = True

class DelayManager:
    """
    Manages timing delays for state changes in the climate control system.
    
    This class handles various delay settings to prevent rapid switching of climate states,
    providing a more stable and efficient operation.
    
    Attributes:
        occupied_delay (int): Delay in seconds before switching to occupied mode
        inoccupied_delay (int): Delay in seconds before switching to unoccupied mode
        opening_delay_open (int): Delay in seconds before responding to an opening event
        opening_delay_close (int): Delay in seconds before responding to a closing event
    """
    def __init__(self, occupied_delay: int = 10, 
                 inoccupied_delay: int = 10,
                 opening_delay_open: int = 300,
                 opening_delay_close: int = 15):
        """
        Initialize the DelayManager with specified delays.
        
        Args:
            occupied_delay: Time to wait before activating occupied mode
            inoccupied_delay: Time to wait before activating unoccupied mode
            opening_delay_open: Time to wait after opening detection
            opening_delay_close: Time to wait after closing detection
        """
        self.occupied_delay = occupied_delay
        self.inoccupied_delay = inoccupied_delay
        self.opening_delay_open = opening_delay_open
        self.opening_delay_close = opening_delay_close

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> 'DelayManager':
        """
        Creates a DelayManager instance from a configuration dictionary.
        
        Args:
            config: Dictionary containing delay configurations
            
        Returns:
            DelayManager: New instance with configured delays
        """
        return cls(
            occupied_delay=config.get('to_occupied_delay', ClimateConstants.DEFAULT_DELAYS['OCCUPIED_DELAY']),
            inoccupied_delay=config.get('to_inoccupied_delay', ClimateConstants.DEFAULT_DELAYS['INOCCUPIED_DELAY']),
            opening_delay_open=config.get('opening_delay_open', ClimateConstants.DEFAULT_DELAYS['OPENING_DELAY_OPEN']),
            opening_delay_close=config.get('opening_delay_close', ClimateConstants.DEFAULT_DELAYS['OPENING_DELAY_CLOSE'])
        )

class TemperatureManager:
    """
    Manages temperature-related operations and validations.
    
    This class handles temperature data processing, validation, and updates,
    ensuring consistent temperature handling across the application.
    
    Attributes:
        hass: Reference to the Home Assistant API
        temperature_day: Current day temperature
    """
    def __init__(self, hass_api):
        """
        Initialize the TemperatureManager.
        
        Args:
            hass_api: Reference to the Home Assistant API instance
        """
        self.hass = hass_api
        self.temperature_day = None

    def validate_temperature(self, temp: Any) -> Optional[float]:
        """
        Validates and converts a temperature value.
        
        Args:
            temp: Temperature value to validate
            
        Returns:
            Optional[float]: Validated temperature or None if invalid
        """
        if temp in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value, None]:
            return None
        try:
            return float(temp)
        except (ValueError, TypeError):
            self.hass.error(f"Invalid temperature: {temp}")
            return None

    def update_temperature_day(self, new_temp: str) -> None:
        """
        Updates the daily temperature value.
        
        Args:
            new_temp: New temperature value to set
        """
        if new_temp in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value]:
            self.hass.log(f"Outdoor temperature is {new_temp}, using None as value")
            self.temperature_day = None
        else:
            self.temperature_day = self.hass.int(new_temp)

class EntityValidator:
    """
    Validator for Home Assistant entities and configurations.
    
    This class provides validation methods for entities and configurations,
    ensuring that all required components exist and are properly configured
    before the system attempts to use them.
    
    Attributes:
        hass: Reference to the Home Assistant API
    """
    def __init__(self, hass_api):
        """
        Initialize the EntityValidator.
        
        Args:
            hass_api: Reference to the Home Assistant API instance
        """
        self.hass = hass_api

    def validate_entity(self, entity_id: str, context: str = "") -> bool:
        """
        Validates the existence of a Home Assistant entity.
        
        Args:
            entity_id: The ID of the entity to validate
            context: Optional context string for error messages
            
        Returns:
            bool: True if entity exists, False otherwise
        """
        if not self.hass.entity_exists(entity_id):
            self.hass.error(f"{context}: Entity {entity_id} does not exist")
            return False
        return True

    def validate_climate_config(self, climate: Dict[str, Any], index: int) -> bool:
        """
        Validates a climate unit configuration.
        
        Args:
            climate: Dictionary containing climate configuration
            index: Index of the climate unit for error messages
            
        Returns:
            bool: True if configuration is valid
            
        Raises:
            ValueError: If required configuration elements are missing
        """
        if 'climate_entity' not in climate:
            raise ValueError(f"Invalid configuration: 'climate_entity' missing for unit {index}")
        return self.validate_entity(climate['climate_entity'], f"Climate {index}")

class ClimateConfig(TypedDict):
    """
    Type definition for climate configuration.
    
    This TypedDict defines the structure of a climate unit configuration,
    ensuring type safety and proper documentation of configuration options.
    
    Attributes:
        climate_entity: Entity ID of the climate device
        occupancy_entity: Optional entity ID for occupancy sensor
        opening_entity: Optional entity ID for window/door sensor
        external_temperature_entity: Optional entity ID for external temperature sensor
        heating_limit: Optional temperature limit for heating
    """
    climate_entity: str
    occupancy_entity: Optional[str]
    opening_entity: Optional[str]
    external_temperature_entity: Optional[str]
    heating_limit: Optional[float]

class ClimateConstants:
    """
    Constants used throughout the climate control system.
    
    This class defines default values and constants used by the climate control system,
    centralizing configuration defaults and making them easily maintainable.
    
    Attributes:
        DEFAULT_SETPOINTS: Default temperature setpoints for different modes
        DEFAULT_DELAYS: Default delay times for various state changes
        DEFAULT_HEATING_LIMIT: Default temperature limit for heating
    """
    
    # Default temperatures for different modes (in °C)
    DEFAULT_SETPOINTS = {
        'occupied': 19,  # Normal operation temperature when room is occupied
        'away': 17,     # Economy temperature when room is unoccupied
        'off': 7        # Frost protection temperature
    }

    # Default delays (in seconds)
    DEFAULT_DELAYS = {
        'OCCUPIED_DELAY': 10,         # Delay before switching to occupied mode
        'INOCCUPIED_DELAY': 10,      # Delay before switching to unoccupied mode
        'OPENING_DELAY_OPEN': 300,    # Delay after opening detection (5 minutes)
        'OPENING_DELAY_CLOSE': 15     # Delay after closing detection
    }

    # Default heating limit temperature (in °C)
    DEFAULT_HEATING_LIMIT = 19

class ClimateState(Enum):
    """
    Enumeration of possible climate states.
    
    This enum defines the standard states that a climate unit can be in,
    ensuring consistent state handling across the application.
    """
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"

class ClimateConfiguration:
    """
    Configuration class for climate units.
    
    This class handles the configuration of individual climate units,
    providing a structured way to store and access climate settings.
    
    Attributes:
        climate_entity: Entity ID of the climate device
        occupancy_entity: Optional entity ID for occupancy sensor
        opening_entity: Optional entity ID for window/door sensor
    """
    def __init__(self, config_dict: Dict[str, Any]):
        """
        Initialize climate configuration from dictionary.
        
        Args:
            config_dict: Dictionary containing climate configuration
        """
        self.climate_entity = config_dict['climate_entity']
        self.occupancy_entity = config_dict.get('occupancy_entity')
        # etc...

class FullAutomationClimate(hass.Hass):
    """
    Main class managing climate automation.
    Inherits from AppDaemon's Hass class to interact with Home Assistant.
    
    This class is responsible for:
    - Initializing and managing climate units
    - Handling state changes and events
    - Coordinating temperature adjustments
    - Managing occupancy and opening states
    - Logging and error handling
    """

    def initialize(self) -> None:
        """
        Initializes the climate automation system.
        
        This method:
        1. Sets up debug logging
        2. Validates configuration
        3. Initializes managers and validators
        4. Sets up climate units
        5. Configures event listeners
        
        Raises:
            ValueError: If configuration is invalid
        """
        try:
            self.debug = self.args.get('debug', False)
            self._print_banner()
            
            if 'climates' not in self.args:
                raise ValueError("Invalid configuration: 'climates' parameter required")

            self.entity_validator = EntityValidator(self)
            self.temp_manager = TemperatureManager(self)
            
            self._init_global_config()
            self._init_outdoor_temperature()
            self.climates = self.init_climates()
            
            for climate_index, climate in enumerate(self.climates):
                self._setup_temperature_entity_listeners(climate_index)
                self.set_climate(climate_index)
                
            self.log("Successfully initialized")
            
        except Exception as e:
            self.error(f"Error during initialization: {str(e)}")
            self.error(f"Traceback: {traceback.format_exc()}")

    def _print_banner(self) -> None:
        """
        Displays the startup banner in the log.
        
        This method prints a formatted banner to the log when the application starts,
        making it easier to identify the start of a new session in the logs.
        """
        self.log("#----------------------------#")
        self.log("|  Full Automation Climates  |")
        self.log("#----------------------------#")
        self.log("")

    def _init_global_config(self) -> None:
        """
        Initializes global configuration settings.
        
        This method sets up:
        - Global temperature setpoints
        - Global setpoint entities
        - Listeners for global temperature entities
        """
        self.global_setpoints = {
            'occupied': self.args.get('occupied_heating_setpoint'),
            'away': self.args.get('away_heating_setpoint'),
            'off': self.args.get('off_heating_setpoint')
        }
        
        self.global_setpoint_entities = {
            'occupied': self.args.get('occupied_heating_setpoint_entity'),
            'away': self.args.get('away_heating_setpoint_entity'),
            'off': self.args.get('off_heating_setpoint_entity')
        }

        # Configure listeners for global entities
        for mode, entity in self.global_setpoint_entities.items():
            if entity and self.entity_exists(entity):
                self.listen_state(
                    self.callback_global_temperature_entity,
                    entity,
                    mode=mode,
                    duration=1
                )

    def _init_outdoor_temperature(self) -> None:
        """
        Initializes outdoor temperature monitoring.
        
        This method:
        - Validates outdoor temperature entity
        - Sets up state listeners
        - Initializes current temperature value
        - Handles missing or invalid temperature entities
        """
        if 'outdoor_temperature_entity' not in self.args:
            return

        outdoor_temp_entity = self.args['outdoor_temperature_entity']
        self.debug_log(f"Init outdoor temperature: {outdoor_temp_entity}")
        
        if not self.entity_validator.validate_entity(outdoor_temp_entity):
            return
            
        self.listen_state(self.get_temperature_day, outdoor_temp_entity)
        current_temp = self.get_state(outdoor_temp_entity)
        
        if current_temp not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value]:
            self.temp_manager.temperature_day = self.int(current_temp)
            
        self.debug_log(f"Outdoor temperature: {self.temp_manager.temperature_day}")

    def _setup_temperature_entity_listeners(self, climate_index: int) -> None:
        """
        Sets up listeners for temperature entities with a one-second delay.
        
        Args:
            climate_index: Index of the climate unit in the climates list
            
        This method:
        - Sets up listeners for temperature setpoint entities
        - Validates entity existence
        - Configures callbacks with appropriate delays
        """
        climate = self.climates[climate_index]
        for mode in ['occupied', 'away', 'off']:
            entity_key = f'{mode}_heating_setpoint_entity'
            if entity_key in climate and climate[entity_key]:
                if not self.entity_exists(climate[entity_key]):
                    self.error(f"Entity {climate[entity_key]} does not exist")
                    continue
                self.listen_state(
                    self.callback_temperature_entity,
                    climate[entity_key],
                    climate_index=climate_index,
                    mode=mode,
                    duration=1
                )

    def callback_temperature_entity(self, entity, attribute, old, new, kwargs):
        """
        Callback handler for temperature entity changes.
        
        Args:
            entity: Entity that triggered the callback
            attribute: Changed attribute
            old: Previous value
            new: New value
            kwargs: Additional callback parameters
            
        This method updates the climate unit when temperature setpoints change.
        """
        if new not in ['unknown', 'unavailable']:
            self.set_climate(kwargs['climate_index'])

    def callback_global_temperature_entity(self, entity, attribute, old, new, kwargs):
        """
        Callback handler for global temperature entity changes.
        
        Args:
            entity: Entity that triggered the callback
            attribute: Changed attribute
            old: Previous value
            new: New value
            kwargs: Additional callback parameters
            
        This method updates all climate units that use the global temperature entity.
        """
        if new not in ['unknown', 'unavailable']:
            # Update all climate units using this global entity
            for climate_index, climate in enumerate(self.climates):
                entity_key = f'{kwargs["mode"]}_heating_setpoint_entity'
                if entity_key not in climate or not climate[entity_key]:
                    self.set_climate(climate_index)

    def _get_temperature_setpoint(self, climate: Dict[str, Any], mode: str) -> float:
        """
        Determines temperature setpoint according to configuration hierarchy.
        
        Args:
            climate: Climate unit configuration dictionary
            mode: Operating mode ('occupied', 'away', or 'off')
            
        Returns:
            float: Temperature setpoint to apply
            
        This method implements the following hierarchy:
        1. Local entity value if available
        2. Local fixed value if defined
        3. Global entity value if available
        4. Global fixed value if defined
        5. Default constant value as fallback
        """
        entity_key = f'{mode}_heating_setpoint_entity'
        setpoint_key = f'{mode}_heating_setpoint'
        
        # Check local entity
        if entity_key in climate and climate[entity_key]:
            temp = self.get_state(climate[entity_key])
            validated_temp = self.temp_manager.validate_temperature(temp)
            if validated_temp is not None:
                return validated_temp
        
        # Check local fixed value
        if setpoint_key in climate:
            try:
                return float(climate[setpoint_key])
            except (ValueError, TypeError):
                self.error(f"Unable to convert fixed temperature {setpoint_key} to number: {climate[setpoint_key]}")
        
        # Check global entity
        if self.global_setpoint_entities[mode]:
            temp = self.get_state(self.global_setpoint_entities[mode])
            if temp not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value, None]:
                try:
                    return float(temp)
                except (ValueError, TypeError):
                    self.error(f"Unable to convert global temperature of {self.global_setpoint_entities[mode]} to number: {temp}")
        
        # Check global fixed value
        if self.global_setpoints[mode] is not None:
            try:
                return float(self.global_setpoints[mode])
            except (ValueError, TypeError):
                self.error(f"Unable to convert global fixed temperature {mode} to number: {self.global_setpoints[mode]}")
        
        # Default value
        return float(ClimateConstants.DEFAULT_SETPOINTS[mode])

    def set_climate(self, climate_index: int) -> None:
        """
        Configures a climate unit with error handling.
        
        Args:
            climate_index: Index of the climate unit to configure
            
        This method:
        1. Validates climate entity
        2. Determines appropriate temperature
        3. Applies configuration to the climate unit
        4. Handles errors and logs issues
        """
        try:
            climate = self.climates[climate_index]
            climate_entity = climate['climate_entity']
            self.debug_log(f"Set climate : {climate_entity}")

            if not self.entity_exists(climate_entity):
                self.error(f"Entity {climate_entity} does not exist")
                return

            if climate_entity.split('.')[0] != 'climate':
                self._handle_non_climate_entity(climate_index, climate_entity)
                return

            # Determine temperature
            if climate['is_opening']:
                target_temp = self._get_temperature_setpoint(climate, 'off')
            else:
                target_temp = self._get_temperature_setpoint(climate, 'occupied' if climate.get('occupancy', True) else 'away')

            # Apply temperature
            current_temp = self.get_state(climate_entity, attribute='temperature')
            if current_temp != target_temp:
                self.call_service("climate/set_temperature", entity_id=climate_entity, temperature=target_temp)
                self.debug_log(f"  Set temperature to {target_temp}")

        except Exception as e:
            self.error(f"Error while configuring climate unit {climate_index}: {str(e)}")
            self.error(f"Traceback : {traceback.format_exc()}")

    def init_climates(self) -> List[Dict[str, Any]]:
        climates = self.list(self.args['climates']).copy()
        # Initialiser self.climates avant la configuration
        self.climates = climates
        
        for climate_index, climate in enumerate(climates):
            self._validate_climate_config(climate, climate_index)
            self._setup_occupancy(climate, climate_index)
            self._setup_openings(climate, climate_index)
            self._setup_temperature(climate, climate_index)
            self._setup_heating_limit(climate, climate_index)
        return climates

    def _validate_climate_config(self, climate: Dict[str, Any], climate_index: int) -> None:
        """Valide la configuration d'un climatiseur."""
        if 'climate_entity' not in climate:
            raise ValueError(f"Invalid configuration: 'climate_entity' is missing for climate unit {climate_index}")
            
        climate_entity = climate['climate_entity']
        self.debug_log(f"Init climate : {climate_entity}")
        
        if not self.entity_exists(climate_entity):
            self.error(f"Entity {climate_entity} does not exist")
            return False
        return True

    def _setup_occupancy(self, climate: Dict[str, Any], climate_index: int) -> None:
        """Configure la détection de présence pour un climatiseur."""
        if 'occupancy_entity' not in climate:
            return
            
        if not self.entity_exists(climate['occupancy_entity']):
            self.error(f"Entity {climate['occupancy_entity']} does not exist")
            return
            
        self.debug_log(f"  Init occupancy : {climate['occupancy_entity']}")
        to_occupied_delay = climate.get('to_occupied_delay', ClimateConstants.DEFAULT_DELAYS['OCCUPIED_DELAY'])
        to_inoccupied_delay = climate.get('to_inoccupied_delay', ClimateConstants.DEFAULT_DELAYS['INOCCUPIED_DELAY'])
        
        try:
            if to_occupied_delay == 0 and to_inoccupied_delay == 0:
                self.listen_state(self.callback_occupancy, climate['occupancy_entity'], climate_index=climate_index)
            else:
                self.listen_state(self.callback_occupancy, climate['occupancy_entity'], 
                                new='on', climate_index=climate_index, duration=to_occupied_delay)
                self.listen_state(self.callback_occupancy, climate['occupancy_entity'], 
                                new='off', climate_index=climate_index, duration=to_inoccupied_delay)
            climate['occupancy'] = self.get_state(climate['occupancy_entity']) in ["on","home",True,"true","True"]
        except Exception as e:
            self.error(f"Error while configuring presence detection: {str(e)}")

    def _setup_openings(self, climate: Dict[str, Any], climate_index: int) -> None:
        """Configure la détection d'ouverture pour un climatiseur."""
        if 'opening_entity' not in climate:
            climate['is_opening'] = False
            return
            
        if not self.entity_exists(climate['opening_entity']):
            self.error(f"Opening entity {climate['opening_entity']} does not exist")
            return
            
        self.debug_log(f"  Init opening : {climate['opening_entity']}")
        opening_delay_open = climate.get('opening_delay_open', ClimateConstants.DEFAULT_DELAYS['OPENING_DELAY_OPEN'])
        opening_delay_close = climate.get('opening_delay_close', ClimateConstants.DEFAULT_DELAYS['OPENING_DELAY_CLOSE'])
        
        try:
            if opening_delay_open == 0 and opening_delay_close == 0:
                self.listen_state(self.callback_opening, climate['opening_entity'], climate_index=climate_index)
            else:
                self.listen_state(self.callback_opening, climate['opening_entity'], 
                                new='on', climate_index=climate_index, duration=opening_delay_open)
                self.listen_state(self.callback_opening, climate['opening_entity'], 
                                new='off', climate_index=climate_index, duration=opening_delay_close)
            climate['is_opening'] = self.get_state(climate['opening_entity']) in ["on","home",True,"true","True"]
        except Exception as e:
            self.error(f"Error while configuring openings: {str(e)}")

    def _setup_temperature(self, climate: Dict[str, Any], climate_index: int) -> None:
        """Configure external temperature for a climate unit."""
        # Check if external_temperature_entity exists
        has_external_temp = 'external_temperature_entity' in climate
        has_external_input = 'external_temperature_input' in climate

        if not has_external_temp:
            return

        # Validate existence of external temperature entity
        if not self.entity_exists(climate['external_temperature_entity']):
            self.error(f"External temperature entity {climate['external_temperature_entity']} does not exist")
            return

        # For climate entities only
        if climate['climate_entity'].startswith('climate.'):
            if not has_external_input:
                self.error(f"external_temperature_input must be defined for climate entities: {climate['climate_entity']} if external_temperature_entity is defined")
                return
            if not self.entity_exists(climate['external_temperature_input']):
                self.error(f"Entity external_temperature_input {climate['external_temperature_input']} does not exist")
                return

        self.debug_log(f"  Init external temperature : {climate['external_temperature_entity']}")
        try:
            # Configure state listener
            self.listen_state(self.callback_external_temperature, 
                            climate['external_temperature_entity'], 
                            climate_index=climate_index)
            
            # Initialize with current temperature
            current_temp = self.get_state(climate['external_temperature_entity'])
            if current_temp not in ['unknown', 'unavailable', None]:
                self.callback_external_temperature(
                    climate['external_temperature_entity'],
                    'state',
                    None,
                    current_temp,
                    {'climate_index': climate_index}
                )
        except Exception as e:
            self.error(f"Error while configuring external temperature: {str(e)}")

    def _setup_heating_limit(self, climate: Dict[str, Any], climate_index: int) -> None:
        """Configure la limite de chauffage pour un climatiseur."""
        if 'heating_limit_entity' not in climate:
            return
            
        if not self.entity_exists(climate['heating_limit_entity']):
            self.error(f"Entity {climate['heating_limit_entity']} does not exist")
            return
            
        self.debug_log(f"  Init heating limit : {climate['heating_limit_entity']}")
        try:
            self.listen_state(self.callback_heating_limit, 
                            climate['heating_limit_entity'], 
                            climate_index=climate_index)
        except Exception as e:
            self.error(f"Error while configuring heating limit: {str(e)}")

    def callback_opening(self, entity, attribute, old, new, kwargs):
        """Callback pour changement d'état d'ouverture"""
        climate_index = kwargs['climate_index']
        self.climates[climate_index]['is_opening'] = new in [
            EntityState.ON.value,
            EntityState.HOME.value,
            EntityState.TRUE_BOOL.value,
            EntityState.TRUE.value
        ]
        self.set_climate(climate_index)

    def callback_external_temperature(self, entity, attribute, old, new, kwargs):
        """Callback for external temperature change"""
        climate = self.climates[kwargs['climate_index']]
        climate_entity = climate['climate_entity']
        
        if not climate_entity.startswith('climate.'):
            return
            
    
        
        self.debug_log(f"Setting external temperature to {new} for {climate_entity}")
        
        if new not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value]:
            try:
                temp_value = float(new)
                self.call_service("number/set_value", 
                                entity_id=climate['external_temperature_input'], 
                                value=temp_value)
                self.debug_log(f"Setting external temperature to {temp_value} for {climate['external_temperature_input']}")
            except ValueError:
                self.error(f"Unable to convert temperature {new} to number for {climate_entity}")
            except Exception as e:
                self.error(f"Error while updating external temperature for {climate_entity}: {str(e)}")

    def callback_occupancy(self, entity, attribute, old, new, kwargs):
        """
        Callback appele lors d'un changement de presence dans une piece.
        Met e jour l'etat d'occupation et ajuste le climatiseur.
        
        Args:
            entity: Capteur de presence
            new: Nouvel etat
            kwargs: Parametres supplementaires
        """
        self.climates[kwargs['climate_index']]['occupancy'] = new in ["on","home",True,"true","True"]
        self.set_climate(kwargs['climate_index'])

    def get_temperature_day(self, entity, attribute, old, new, kwargs):
        """Met à jour la température journalière"""
        self.temp_manager.update_temperature_day(new)
        self.debug_log(f"Outdoor temperature: {self.temp_manager.temperature_day}")
        
        for climate_index in range(len(self.climates)):
            self.set_climate(climate_index)

    def _handle_non_climate_entity(self, climate_index: int, climate_entity: str) -> None:
        """Handles non-climate entities"""
        try:
            current_state = self.get_state(climate_entity)
            climate = self.climates[climate_index]
            
            # Check opening state
            is_opening = self._check_opening_state(climate)
            
            # Check external temperature
            should_turn_off_temp = self._check_external_temperature(climate)

            # Control entity
            if climate['occupancy'] and not is_opening and not should_turn_off_temp:
                if current_state != EntityState.ON.value:
                    self.log(f"Turning on {climate_entity}")
                    self.call_service(f"{climate_entity.split('.')[0]}/turn_on", entity_id=climate_entity)
                    self.debug_log("Set to ON")
            else:
                if current_state != EntityState.OFF.value:
                    self.log(f"Turning off {climate_entity}")
                    self.call_service(f"{climate_entity.split('.')[0]}/turn_off", entity_id=climate_entity)
                    self.debug_log("Set to OFF")
        except Exception as e:
            self.error(f"Error while handling non-climate entity {climate_entity}: {str(e)}")

    def _check_opening_state(self, climate: Dict[str, Any]) -> bool:
        """Checks opening state of an entity"""
        if 'opening_entity' not in climate:
            return False
            
        opening_state = self.get_state(climate['opening_entity'])
        return opening_state in [
            EntityState.ON.value,
            EntityState.HOME.value,
            EntityState.TRUE_BOOL.value,
            EntityState.TRUE.value
        ]

    def _check_external_temperature(self, climate: Dict[str, Any]) -> bool:
        """Checks if external temperature exceeds heating limit"""
        if 'external_temperature_entity' not in climate or not climate['external_temperature_entity']:
            return False
            
        ext_temp = self.get_state(climate['external_temperature_entity'])
        if ext_temp in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value, None]:
            return False
            
        try:
            ext_temp = float(ext_temp)
            heating_limit = self._get_heating_limit(climate)
            return ext_temp >= heating_limit
        except (ValueError, TypeError):
            self.error(f"Unable to convert external temperature {ext_temp} to number")
            return False

    def _get_heating_limit(self, climate: Dict[str, Any]) -> float:
        """Gets heating limit for a climate unit"""
        if 'heating_limit_entity' in climate and climate['heating_limit_entity']:
            limit = self.get_state(climate['heating_limit_entity'])
            if limit not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value, None]:
                try:
                    return float(limit)
                except (ValueError, TypeError):
                    pass
        return climate.get('heating_limit', ClimateConstants.DEFAULT_HEATING_LIMIT)

    def entity_exists(self, entity_id: str) -> bool:
        """
        Checks if an entity exists in Home Assistant.
        
        Args:
            entity_id: Entity ID to check
            
        Returns:
            bool: True if entity exists, False otherwise
        """
        try:
            state = self.get_state(entity_id)
            return state is not None
        except Exception:
            return False

    def error(self, message: str) -> None:
        """
        Logs an error message.
        
        Args:
            message: Error message to log
        """
        self.log(message, level="ERROR")

    def list(self, val: Union[List[Any], Any]) -> List[Any]:
        """
        Converts a value to list if it isn't already one.
        
        Args:
            val: Value to convert
            
        Returns:
            List[Any]: List containing the value or original list
        """
        if isinstance(val, list): return val
        return [val]

    def int(self, val: Union[str, int, float]) -> Union[int, Any]:
        """
        Safely converts a value to integer.
        
        Args:
            val: Value to convert
            
        Returns:
            Union[int, Any]: Value converted to integer or original value if impossible
        """
        if val in ['unknown', 'unavailable']: return 0
        try: return int(float(val))
        except: return val

    def debug_log(self, message: str) -> None:
        """
        Displays a debug message if debug mode is active.
        
        Args:
            message: Message to display
        """
        if self.debug: self.log(message)

    def callback_heating_limit(self, entity, attribute, old, new, kwargs):
        """
        Callback triggered on heating limit change.
        Updates configuration and adjusts climate unit.
        
        Args:
            entity: Heating limit entity
            new: New value
            kwargs: Additional parameters
        """
        self.set_climate(kwargs['climate_index'])

    def log_with_context(self, message: str, level: str = "INFO", context: Optional[str] = None) -> None:
        """Logger avec contexte pour meilleure traçabilité"""
        prefix = f"[{context}] " if context else ""
        self.log(f"{prefix}{message}", level=level)

    def _validate_temperature(self, temp: Any) -> Optional[float]:
        """
        Valide et convertit une température.
        
        Args:
            temp: Valeur de température à valider
            
        Returns:
            Optional[float]: Température convertie en float ou None si invalide
        """
        if temp in ['unknown', 'unavailable', None]:
            return None
        try:
            return float(temp)
        except (ValueError, TypeError):
            self.error(f"Invalid temperature: {temp}")
            return None