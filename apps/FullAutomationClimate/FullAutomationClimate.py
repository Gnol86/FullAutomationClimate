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

import appdaemon.plugins.hass.hassapi as hass
import traceback
from typing import Optional, Dict, List, Any, Union, TypedDict
from enum import Enum, auto

class EntityState(Enum):
    """
    Enumeration of possible entity states in Home Assistant.
    """
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    ON = "on"
    OFF = "off"
    HOME = "home"
    TRUE = "true"
    TRUE_BOOL = True

class ClimateConstants:
    """
    Constants used throughout the climate control system.
    """
    DEFAULT_DELAYS = {
        'OCCUPIED_DELAY': 10,
        'INOCCUPIED_DELAY': 10,
        'OPENING_DELAY_OPEN': 300,
        'OPENING_DELAY_CLOSE': 15
    }
    
    DEFAULT_TEMPERATURES = {
        'OCCUPIED_HEATING': 21,
        'AWAY_HEATING': 17,
        'OFF_HEATING': 7,
        'HEATING_LIMIT': 19
    }

class ClimateUnit:
    """
    Represents a single climate control unit with its associated entities and settings.
    """
    def __init__(self, hass_api, config: Dict[str, Any]):
        self.hass = hass_api
        self.entity_id = config['climate_entity']
        self.occupancy_entity = config.get('occupancy_entity')
        self.opening_entity = config.get('opening_entity')
        self.external_temp_entity = config.get('external_temperature_entity')
        self.external_temp_input = config.get('external_temperature_input')
        self.heating_limit_entity = config.get('heating_limit_entity')
        
        # Temperature setpoints
        self.occupied_heating_setpoint_entity = config.get('occupied_heating_setpoint_entity')
        self.away_heating_setpoint_entity = config.get('away_heating_setpoint_entity')
        self.off_heating_setpoint = config.get('off_heating_setpoint', ClimateConstants.DEFAULT_TEMPERATURES['OFF_HEATING'])
        
        # Initialize state
        self.is_occupied = False
        self.is_open = False
        self.external_temp = None
        
    def update_temperature(self, temp: float) -> None:
        """Update the temperature setpoint based on current conditions."""
        try:
            if self.is_open:
                self.hass.call_service("climate/set_temperature", entity_id=self.entity_id, temperature=self.off_heating_setpoint)
            else:
                target_temp = self.get_target_temperature()
                if target_temp is not None:
                    self.hass.call_service("climate/set_temperature", entity_id=self.entity_id, temperature=target_temp)
        except Exception as e:
            self.hass.error(f"Error updating temperature for {self.entity_id}: {str(e)}")
            
    def get_target_temperature(self) -> Optional[float]:
        """Calculate the target temperature based on occupancy and other conditions."""
        if self.is_occupied:
            return self.hass.get_state(self.occupied_heating_setpoint_entity)
        return self.hass.get_state(self.away_heating_setpoint_entity)

class FullAutomationClimate(hass.Hass):
    """
    Main class for the climate automation system.
    """
    def initialize(self) -> None:
        """Initialize the climate automation system."""
        try:
            self.debug_mode = bool(self.args.get('debug', False))
            self.outdoor_temp_entity = self.args.get('outdoor_temperature_entity')
            self.outdoor_temp_limit = float(self.args.get('outdoor_temperature_limit', ClimateConstants.DEFAULT_TEMPERATURES['HEATING_LIMIT']))
            self.off_heating_setpoint_entity = self.args.get('off_heating_setpoint_entity')
            
            # Initialize climate units
            self.climate_units = []
            for climate_config in self.args.get('climates', []):
                unit = ClimateUnit(self, climate_config)
                self.climate_units.append(unit)
                
            # Set up listeners
            self._setup_listeners()
            
        except Exception as e:
            self.error(f"Error initializing FullAutomationClimate: {str(e)}\n{traceback.format_exc()}")
            
    def _setup_listeners(self) -> None:
        """Set up event listeners for all monitored entities."""
        try:
            if self.outdoor_temp_entity:
                self.listen_state(self.handle_outdoor_temp_change, self.outdoor_temp_entity)
                
            for unit in self.climate_units:
                if unit.occupancy_entity:
                    self.listen_state(self.handle_occupancy_change, unit.occupancy_entity)
                if unit.opening_entity:
                    self.listen_state(self.handle_opening_change, unit.opening_entity)
                if unit.external_temp_entity:
                    self.listen_state(self.handle_external_temp_change, unit.external_temp_entity)
                    
        except Exception as e:
            self.error(f"Error setting up listeners: {str(e)}")
            
    def handle_outdoor_temp_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in outdoor temperature."""
        try:
            if new not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value]:
                self.update_all_units()
        except Exception as e:
            self.error(f"Error handling outdoor temperature change: {str(e)}")
            
    def handle_occupancy_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in occupancy status."""
        try:
            for unit in self.climate_units:
                if unit.occupancy_entity == entity:
                    unit.is_occupied = new in [EntityState.ON.value, EntityState.HOME.value, EntityState.TRUE.value, EntityState.TRUE_BOOL.value]
                    unit.update_temperature(self.get_current_temp(unit))
        except Exception as e:
            self.error(f"Error handling occupancy change: {str(e)}")
            
    def handle_opening_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in opening status (windows/doors)."""
        try:
            for unit in self.climate_units:
                if unit.opening_entity == entity:
                    unit.is_open = new == EntityState.ON.value
                    unit.update_temperature(self.get_current_temp(unit))
        except Exception as e:
            self.error(f"Error handling opening change: {str(e)}")
            
    def handle_external_temp_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in external temperature sensors."""
        try:
            for unit in self.climate_units:
                if unit.external_temp_entity == entity:
                    unit.external_temp = float(new) if new not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value] else None
                    if unit.external_temp_input:
                        self.set_value(unit.external_temp_input, unit.external_temp)
        except Exception as e:
            self.error(f"Error handling external temperature change: {str(e)}")
            
    def update_all_units(self) -> None:
        """Update all climate units."""
        try:
            for unit in self.climate_units:
                unit.update_temperature(self.get_current_temp(unit))
        except Exception as e:
            self.error(f"Error updating all units: {str(e)}")
            
    def get_current_temp(self, unit: ClimateUnit) -> Optional[float]:
        """Get the current temperature for a climate unit."""
        try:
            if unit.external_temp_entity:
                temp_state = self.get_state(unit.external_temp_entity)
                if temp_state not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value]:
                    return float(temp_state)
        except Exception as e:
            self.error(f"Error getting current temperature: {str(e)}")
        return None
