# Full Automation Climate

Un script AppDaemon pour Home Assistant qui gère automatiquement vos climatiseurs.

## Prérequis

-   Home Assistant
-   AppDaemon
-   HACS

## Fonctionnalités

-   Gestion automatique de la température
-   Optimisation de la consommation d'énergie
-   Interface intuitive
-   Automatisation basée sur la présence et les habitudes

## Installation

1. Assurez-vous d'avoir AppDaemon installé et configuré dans Home Assistant
2. Ajoutez ce dépôt à HACS comme dépôt AppDaemon personnalisé
3. Installez "Full Automation Climate" depuis HACS
4. Ajoutez la configuration suivante à votre fichier `apps.yaml` d'AppDaemon :

```yaml
full_automation_climate:
    module: FullAutomationClimates
    class: FullAutomationClimates
    climate_entity: climate.your_climate_entity
    # Ajoutez ici vos autres paramètres de configuration
```

## Configuration

Les paramètres de configuration disponibles sont :

[Liste des paramètres à venir]

## Support

Si vous rencontrez des problèmes ou avez des suggestions, n'hésitez pas à ouvrir une issue sur GitHub.

## License

MIT License
