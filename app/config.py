import json
import os
from dataclasses import dataclass, asdict, field

@dataclass
class TestSettings:
    """Configuration settings for LLM model configuration."""
    # vLLM Connection
    models_endpoint: str = "http://localhost:8000/v1/models"
    model_name: str = "facebook/opt-125m"
    vllm_version: str = ""
    thinking_enabled: bool = False
    expected_format: str = "auto"
    response_cache_enabled: bool = True

@dataclass
class AppConfig:
    """Global application configuration."""
    test_settings: TestSettings = field(default_factory=TestSettings)

class ConfigManager:
    """Manages persistent application configuration via a JSON file."""
    
    def __init__(self, config_path: str = "app/config.json"):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> AppConfig:
        """Loads configuration from the JSON file or returns defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    # Reconstruct nested dataclasses
                    test_settings_data = data.get("test_settings", {})
                    test_settings = TestSettings(**test_settings_data)
                    return AppConfig(test_settings=test_settings)
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                print(f"Error loading config: {e}. Using default configuration.")
        
        return AppConfig()

    def save(self) -> None:
        """Persists the current configuration to the JSON file."""
        try:
            with open(self.config_path, 'w') as f:
                json.dump(asdict(self.config), f, indent=4)
        except IOError as e:
            print(f"Error saving config: {e}")

    @property
    def test_settings(self) -> TestSettings:
        """Access the TestSettings object."""
        return self.config.test_settings

    @test_settings.setter
    def test_settings(self, value: TestSettings) -> None:
        """Set the TestSettings object."""
        self.config.test_settings = value

# Singleton instance for easy access across the app
config_manager = ConfigManager()