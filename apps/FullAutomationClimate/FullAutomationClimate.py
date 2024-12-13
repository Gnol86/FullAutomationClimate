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

Author: @gnol86
License: MIT
Repository: https://github.com/Gnol86/FullAutomationClimate
"""

import appdaemon.plugins.hass.hassapi as hass  # type: ignore
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
        
        self.hass.debug_log(f"Initialized climate unit: {self.entity_id}")
        if self.occupancy_entity:
            self.hass.debug_log(f"  Occupancy entity: {self.occupancy_entity}")
        if self.opening_entity:
            self.hass.debug_log(f"  Opening entity: {self.opening_entity}")
        if self.external_temp_entity:
            self.hass.debug_log(f"  External temperature entity: {self.external_temp_entity}")
        
    def update_temperature(self, temp: float) -> None:
        """Update the temperature setpoint based on current conditions."""
        try:
            self.hass.debug_log(f"Updating temperature for {self.entity_id}")
            if self.is_open:
                self.hass.debug_log(f"  Opening detected, setting to off temperature: {self.off_heating_setpoint}")
                self.hass.call_service("climate/set_temperature", entity_id=self.entity_id, temperature=self.off_heating_setpoint)
            else:
                target_temp = self.get_target_temperature()
                if target_temp is not None:
                    self.hass.debug_log(f"  Setting temperature to: {target_temp}")
                    self.hass.call_service("climate/set_temperature", entity_id=self.entity_id, temperature=target_temp)
        except Exception as e:
            self.hass.error(f"Error updating temperature for {self.entity_id}: {str(e)}")
            
    def get_target_temperature(self) -> Optional[float]:
        """Calculate the target temperature based on occupancy and other conditions."""
        if self.is_occupied:
            temp = self.hass.get_state(self.occupied_heating_setpoint_entity)
            self.hass.debug_log(f"  Room occupied, target temperature: {temp}")
            return temp
        temp = self.hass.get_state(self.away_heating_setpoint_entity)
        self.hass.debug_log(f"  Room unoccupied, target temperature: {temp}")
        return temp

class FullAutomationClimate(hass.Hass):
    """
    Main class for the climate automation system.
    """
    def initialize(self) -> None:
        """Initialize the climate automation system."""
        try:
            self.log("#----------------------------#")
            self.log("|  Full Automation Climate   |")
            self.log("#----------------------------#")
            self.log("")
            
            self.debug_mode = bool(self.args.get('debug', False))
            self.outdoor_temp_entity = self.args.get('outdoor_temperature_entity')
            self.outdoor_temp_limit = float(self.args.get('outdoor_temperature_limit', ClimateConstants.DEFAULT_TEMPERATURES['HEATING_LIMIT']))
            self.off_heating_setpoint_entity = self.args.get('off_heating_setpoint_entity')
            
            self.debug_log("Initializing climate automation system")
            if self.outdoor_temp_entity:
                self.debug_log(f"Outdoor temperature entity: {self.outdoor_temp_entity}")
            self.debug_log(f"Outdoor temperature limit: {self.outdoor_temp_limit}")
            
            # Initialize climate units
            self.climate_units = []
            for climate_config in self.args.get('climates', []):
                unit = ClimateUnit(self, climate_config)
                self.climate_units.append(unit)
                
                # Initialize external temperature inputs
                if unit.external_temp_entity and unit.external_temp_input:
                    temp_state = self.get_state(unit.external_temp_entity)
                    if temp_state not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value]:
                        self.set_value(unit.external_temp_input, float(temp_state))
                        self.debug_log(f" Initialized external temperature input {unit.external_temp_input} with value {temp_state}")
                
            # Set up listeners
            self._setup_listeners()
            
            self.log("Successfully initialized")
            
        except Exception as e:
            self.error(f"Error initializing FullAutomationClimate: {str(e)}\n{traceback.format_exc()}")
            
    def _setup_listeners(self) -> None:
        """Set up event listeners for all monitored entities."""
        try:
            self.debug_log("Setting up event listeners")
            if self.outdoor_temp_entity:
                self.listen_state(self.handle_outdoor_temp_change, self.outdoor_temp_entity)
                self.debug_log(f"  Added listener for outdoor temperature: {self.outdoor_temp_entity}")
                
            for unit in self.climate_units:
                if unit.occupancy_entity:
                    self.listen_state(self.handle_occupancy_change, unit.occupancy_entity)
                    self.debug_log(f"  Added occupancy listener for: {unit.occupancy_entity}")
                if unit.opening_entity:
                    self.listen_state(self.handle_opening_change, unit.opening_entity)
                    self.debug_log(f"  Added opening listener for: {unit.opening_entity}")
                if unit.external_temp_entity:
                    self.listen_state(self.handle_external_temp_change, unit.external_temp_entity)
                    self.debug_log(f"  Added external temperature listener for: {unit.external_temp_entity}")
                    
        except Exception as e:
            self.error(f"Error setting up listeners: {str(e)}")
            
    def handle_outdoor_temp_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in outdoor temperature."""
        try:
            self.debug_log(f"Outdoor temperature changed: {new}")
            if new not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value]:
                self.update_all_units()
        except Exception as e:
            self.error(f"Error handling outdoor temperature change: {str(e)}")
            
    def handle_occupancy_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in occupancy status."""
        try:
            self.debug_log(f"Occupancy changed for {entity}: {new}")
            for unit in self.climate_units:
                if unit.occupancy_entity == entity:
                    unit.is_occupied = new in [EntityState.ON.value, EntityState.HOME.value, EntityState.TRUE.value, EntityState.TRUE_BOOL.value]
                    self.debug_log(f"  Updating {unit.entity_id}, occupied: {unit.is_occupied}")
                    unit.update_temperature(self.get_current_temp(unit))
        except Exception as e:
            self.error(f"Error handling occupancy change: {str(e)}")
            
    def handle_opening_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in opening status (windows/doors)."""
        try:
            self.debug_log(f"Opening status changed for {entity}: {new}")
            for unit in self.climate_units:
                if unit.opening_entity == entity:
                    unit.is_open = new == EntityState.ON.value
                    self.debug_log(f"  Updating {unit.entity_id}, open: {unit.is_open}")
                    unit.update_temperature(self.get_current_temp(unit))
        except Exception as e:
            self.error(f"Error handling opening change: {str(e)}")
            
    def handle_external_temp_change(self, entity: str, attribute: Any, old: str, new: str, kwargs: Dict[str, Any]) -> None:
        """Handle changes in external temperature sensors."""
        try:
            self.debug_log(f"External temperature changed for {entity}: {new}")
            for unit in self.climate_units:
                if unit.external_temp_entity == entity:
                    unit.external_temp = float(new) if new not in [EntityState.UNKNOWN.value, EntityState.UNAVAILABLE.value] else None
                    self.debug_log(f"  Updating {unit.entity_id}, external temperature: {unit.external_temp}")
                    if unit.external_temp_input and not kwargs.get('from_input'):
                        self.set_value(unit.external_temp_input, unit.external_temp)
                        self.debug_log(f"  Set external temperature input: {unit.external_temp_input} to {unit.external_temp}")
                    unit.update_temperature(self.get_current_temp(unit))
        except Exception as e:
            self.error(f"Error handling external temperature change: {str(e)}")
            
    def update_all_units(self) -> None:
        """Update all climate units."""
        try:
            self.debug_log("Updating all climate units")
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
                    self.debug_log(f"Current temperature for {unit.entity_id}: {temp_state}")
                    return float(temp_state)
        except Exception as e:
            self.error(f"Error getting current temperature: {str(e)}")
        return None

    def debug_log(self, message: str) -> None:
        """Log a debug message if debug mode is enabled."""
        if self.debug_mode:
            self.log(message)

    def error(self, message: str) -> None:
        """Log an error message."""
        self.log(message, level="ERROR")
