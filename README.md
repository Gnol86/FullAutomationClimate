# Full Automation Climate

An advanced AppDaemon script for Home Assistant that provides intelligent and automated climate control management.

## Features

-   **Multi-Zone Management**: Control multiple climate units independently
-   **Smart Occupancy Control**: Automatically adjusts temperature based on room occupancy
-   **Window/Door Integration**: Adapts climate control when windows or doors are opened
-   **External Temperature Monitoring**: Considers outdoor temperature for optimal efficiency
-   **Flexible Device Support**: Works with both climate entities and simple on/off heating devices
-   **Configurable Delays**: Prevents rapid switching with customizable delays
-   **Temperature Hierarchy**: Global and local temperature setpoints with fallback system
-   **Energy Optimization**: Heating limits based on external temperature
-   **Detailed Logging**: Debug mode for troubleshooting

## Prerequisites

-   Home Assistant
-   AppDaemon
-   HACS (for easy installation)
-   Compatible climate devices and/or switches
-   Optional but recommended:
    -   Occupancy sensors
    -   Door/window sensors
    -   Temperature sensors

## Installation

1. Install AppDaemon if not already installed
2. Add this repository to HACS as a custom AppDaemon repository
3. Install "Full Automation Climate" from HACS
4. Configure your `apps.yaml` file as described below

## Configuration

### Basic Configuration

```yaml
FullAutomationClimate:
    module: FullAutomationClimate
    class: FullAutomationClimate
    debug: true # Optional: Enable detailed logging

    # Global Temperature Settings
    outdoor_temperature_entity: sensor.your_outdoor_temp # Optional
    outdoor_temperature_limit: 19 # Optional: Global heating limit
    off_heating_setpoint_entity: input_number.global_off_heating_setpoint # Optional
    occupied_heating_setpoint: 21 # Optional: Global occupied temperature
    away_heating_setpoint: 17 # Optional: Global away temperature
    off_heating_setpoint: 7 # Optional: Global frost protection temperature

    # Global Mode Settings
    preset_mode: "manual" # Optional: Default preset mode
    hvac_mode: "heat" # Optional: Default HVAC mode

    # Climate Units Configuration
    climates:
        - climate_entity: climate.living_room
          # ... climate unit configuration (see below)
```

### Climate Unit Configuration

Each climate unit supports the following parameters:

```yaml
climates:
    - climate_entity: climate.living_room # Required: Climate entity or switch

      # Temperature Settings
      external_temperature_entity: sensor.living_room_temp # Optional: Room temperature sensor
      external_temperature_input: number.living_room_temp_input # Required if using external_temperature_entity with climate entities
      heating_limit_entity: input_number.living_room_heating_limit # Optional: Individual heating limit
      occupied_heating_setpoint_entity: input_number.living_room_occupied_temp # Optional
      away_heating_setpoint_entity: input_number.living_room_away_temp # Optional
      occupied_heating_setpoint: 21 # Optional: Fixed occupied temperature
      away_heating_setpoint: 17 # Optional: Fixed away temperature
      off_heating_setpoint: 7 # Optional: Fixed frost protection temperature

      # Sensors
      occupancy_entity: binary_sensor.living_room_presence # Optional
      opening_entity: binary_sensor.living_room_window # Optional

      # Delays (in seconds)
      to_occupied_delay: 10 # Optional: Delay before switching to occupied mode
      to_inoccupied_delay: 10 # Optional: Delay before switching to unoccupied mode
      opening_delay_open: 300 # Optional: Delay after opening detection
      opening_delay_close: 15 # Optional: Delay after closing detection

      # Mode Settings (override global settings)
      preset_mode: "manual" # Optional: Override global preset mode
      hvac_mode: "heat" # Optional: Override global HVAC mode
```

### Configuration Parameters

#### Global Parameters

-   `debug`: Enable detailed logging (default: false)
-   `outdoor_temperature_entity`: Entity for outdoor temperature
-   `outdoor_temperature_limit`: Global temperature limit for heating (default: 19°C)
-   `off_heating_setpoint_entity`: Entity for global frost protection temperature
-   `occupied_heating_setpoint`: Global occupied temperature setpoint (default: 19°C)
-   `away_heating_setpoint`: Global away temperature setpoint (default: 17°C)
-   `off_heating_setpoint`: Global frost protection temperature (default: 7°C)
-   `preset_mode`: Default preset mode for climate entities (default: "manual")
-   `hvac_mode`: Default HVAC mode for climate entities (default: "heat")

#### Per Climate Unit Parameters

-   `climate_entity`: Your climate or switch entity (required)
-   `external_temperature_entity`: Temperature sensor for the room
-   `external_temperature_input`: Input entity for external temperature (required for climate entities when using external_temperature_entity)
-   `heating_limit_entity`: Individual heating limit entity
-   `occupied_heating_setpoint_entity`: Entity for occupied temperature setpoint
-   `away_heating_setpoint_entity`: Entity for away temperature setpoint
-   `occupancy_entity`: Presence detection sensor
-   `opening_entity`: Window/door sensor
-   `preset_mode`: Override global preset mode
-   `hvac_mode`: Override global HVAC mode

#### Fixed Temperature Values

-   `occupied_heating_setpoint`: Fixed occupied temperature (per climate unit)
-   `away_heating_setpoint`: Fixed away temperature (per climate unit)
-   `off_heating_setpoint`: Fixed frost protection temperature (per climate unit)

#### Delay Parameters (in seconds)

-   `to_occupied_delay`: Delay before switching to occupied mode (default: 10s)
-   `to_inoccupied_delay`: Delay before switching to unoccupied mode (default: 10s)
-   `opening_delay_open`: Delay after opening detection (default: 300s)
-   `opening_delay_close`: Delay after closing detection (default: 15s)

### Temperature Hierarchy

The system determines temperature setpoints in the following order:

1. Local entity value (e.g., `occupied_heating_setpoint_entity`)
2. Local fixed value (e.g., `occupied_heating_setpoint`)
3. Global entity value
4. Global fixed value
5. Default constant value

### Mode Hierarchy

Operating modes are determined in the following order:

1. Local mode setting (per climate unit)
2. Global mode setting
3. Default mode constants

## Operation

The system operates based on the following hierarchy:

1. Window/Door Status: Takes precedence (turns off when open)
2. Occupancy Status: Determines temperature setpoint (occupied/away)
3. External Temperature: Considers heating limits
4. Temperature Setpoints: Uses local > global > default values

## Support

If you encounter any issues or have suggestions:

1. Enable debug mode for detailed logging
2. Check the AppDaemon logs
3. Open an issue on GitHub with the relevant log information

## License

MIT License - See LICENSE file for details
