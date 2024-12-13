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

### Minimal Configuration

```yaml
FullAutomationClimate:
    module: FullAutomationClimate
    class: FullAutomationClimate
    climates:
        - climate_entity: climate.living_room
          occupancy_entity: binary_sensor.living_room_presence
```

### Basic Configuration Example

```yaml
FullAutomationClimate:
    module: FullAutomationClimate
    class: FullAutomationClimate
    debug: true

    # Global Temperature Settings
    outdoor_temperature_entity: sensor.your_outdoor_temp
    outdoor_temperature_limit: 19
    off_heating_setpoint_entity: input_number.global_off_heating_setpoint
    occupied_heating_setpoint: 21
    away_heating_setpoint: 17
    off_heating_setpoint: 7

    # Global Mode Settings
    preset_mode: "manual"
    hvac_mode: "heat"

    # Climate Units Configuration
    climates:
        - climate_entity: climate.living_room
          # ... climate unit configuration
```

### Climate Unit Configuration Example

```yaml
climates:
    - climate_entity: climate.living_room

      # Temperature Settings
      external_temperature_entity: sensor.living_room_temp
      external_temperature_input: number.living_room_temp_input
      heating_limit_entity: input_number.living_room_heating_limit
      occupied_heating_setpoint_entity: input_number.living_room_occupied_temp
      away_heating_setpoint_entity: input_number.living_room_away_temp
      occupied_heating_setpoint: 21
      away_heating_setpoint: 17
      off_heating_setpoint: 7

      # Sensors
      occupancy_entity: binary_sensor.living_room_presence
      opening_entity: binary_sensor.living_room_window

      # Delays
      to_occupied_delay: 10
      to_inoccupied_delay: 10
      opening_delay_open: 300
      opening_delay_close: 15

      # Mode Settings
      preset_mode: "manual"
      hvac_mode: "heat"
```

### Configuration Parameters

#### Global Parameters

| Parameter                     | Type    | Required | Default    | Description                                    |
| ----------------------------- | ------- | -------- | ---------- | ---------------------------------------------- |
| `debug`                       | boolean | No       | `false`    | Enable detailed logging                        |
| `outdoor_temperature_entity`  | string  | No       | -          | Entity for outdoor temperature                 |
| `outdoor_temperature_limit`   | number  | No       | `19`       | Global heating limit temperature (°C)          |
| `off_heating_setpoint_entity` | string  | No       | -          | Entity for global frost protection temperature |
| `occupied_heating_setpoint`   | number  | No       | `19`       | Global occupied temperature setpoint (°C)      |
| `away_heating_setpoint`       | number  | No       | `17`       | Global away temperature setpoint (°C)          |
| `off_heating_setpoint`        | number  | No       | `7`        | Global frost protection temperature (°C)       |
| `preset_mode`                 | string  | No       | `"manual"` | Default preset mode for climate entities       |
| `hvac_mode`                   | string  | No       | `"heat"`   | Default HVAC mode for climate entities         |

#### Per Climate Unit Parameters

| Parameter                          | Type   | Required  | Default        | Description                                                                                                   |
| ---------------------------------- | ------ | --------- | -------------- | ------------------------------------------------------------------------------------------------------------- |
| `climate_entity`                   | string | Yes       | -              | Climate entity or switch to control                                                                           |
| `external_temperature_entity`      | string | No        | -              | Temperature sensor for the room                                                                               |
| `external_temperature_input`       | string | Special\* | -              | Input entity for external temperature (\*Required if using external_temperature_entity with climate entities) |
| `heating_limit_entity`             | string | No        | -              | Individual heating limit entity                                                                               |
| `occupied_heating_setpoint_entity` | string | No        | -              | Entity for occupied temperature setpoint                                                                      |
| `away_heating_setpoint_entity`     | string | No        | -              | Entity for away temperature setpoint                                                                          |
| `occupancy_entity`                 | string | No        | -              | Presence detection sensor                                                                                     |
| `opening_entity`                   | string | No        | -              | Window/door sensor                                                                                            |
| `preset_mode`                      | string | No        | Global setting | Override global preset mode                                                                                   |
| `hvac_mode`                        | string | No        | Global setting | Override global HVAC mode                                                                                     |

#### Fixed Temperature Values (Per Climate Unit)

| Parameter                   | Type   | Required | Default | Description                        |
| --------------------------- | ------ | -------- | ------- | ---------------------------------- |
| `occupied_heating_setpoint` | number | No       | `19`    | Fixed occupied temperature         |
| `away_heating_setpoint`     | number | No       | `17`    | Fixed away temperature             |
| `off_heating_setpoint`      | number | No       | `7`     | Fixed frost protection temperature |

#### Delay Parameters (Per Climate Unit)

| Parameter             | Type   | Required | Default | Description                                         |
| --------------------- | ------ | -------- | ------- | --------------------------------------------------- |
| `to_occupied_delay`   | number | No       | `10`    | Delay before switching to occupied mode (seconds)   |
| `to_inoccupied_delay` | number | No       | `10`    | Delay before switching to unoccupied mode (seconds) |
| `opening_delay_open`  | number | No       | `300`   | Delay after opening detection (seconds)             |
| `opening_delay_close` | number | No       | `15`    | Delay after closing detection (seconds)             |

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
