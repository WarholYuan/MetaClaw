"""Example weather plugin entrypoint."""


class WeatherPlugin:
    """Minimal plugin class used by the example manifest."""

    def __init__(self, config=None):
        self.config = config or {}

    def get_default_location(self):
        return self.config.get("default_location", "")
