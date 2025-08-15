"""Configuration loader for Treasury Agent tools"""

import os
import yaml
from typing import Dict, Any, Union
from pathlib import Path


class TreasuryConfig:
    """Configuration manager for Treasury Agent tools"""
    
    def __init__(self, config_file: str = None):
        """Initialize configuration loader"""
        if config_file is None:
            config_dir = Path(__file__).parent
            config_file = config_dir / "tool_config.yaml"
        
        self.config_file = Path(config_file)
        self._config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file with environment variable substitution"""
        try:
            with open(self.config_file, 'r') as f:
                content = f.read()
            
            # Simple environment variable substitution
            content = self._substitute_env_vars(content)
            
            return yaml.safe_load(content)
        except FileNotFoundError:
            print(f"Config file not found: {self.config_file}. Using defaults.")
            return self._default_config()
        except Exception as e:
            print(f"Error loading config: {e}. Using defaults.")
            return self._default_config()
    
    def _substitute_env_vars(self, content: str) -> str:
        """Substitute environment variables in config content"""
        import re
        
        def replacer(match):
            env_var = match.group(1)
            default_val = match.group(2) if match.group(2) else ""
            return os.environ.get(env_var, default_val)
        
        # Pattern: ${ENV_VAR:default_value}
        pattern = r'\$\{([^:}]+):([^}]*)\}'
        return re.sub(pattern, replacer, content)
    
    def _default_config(self) -> Dict[str, Any]:
        """Return default configuration if file loading fails"""
        return {
            "payment_executor": {
                "processing_fee_rate": 0.001,
                "default_currency": "USDT",
                "simulation_mode": True
            },
            "investment_allocator": {
                "execution_fee_rate": 0.001,
                "min_recommendation_threshold": 1000,
                "default_risk_tolerance": "medium"
            }
        }
    
    def get_payment_config(self) -> Dict[str, Any]:
        """Get payment executor configuration"""
        return self._config.get("payment_executor", {})
    
    def get_investment_config(self) -> Dict[str, Any]:
        """Get investment allocator configuration"""
        return self._config.get("investment_allocator", {})
    
    def get_processing_fee_rate(self) -> float:
        """Get processing fee rate for payments"""
        env_override = os.environ.get("TREASURY_PROCESSING_FEE_RATE")
        if env_override:
            return float(env_override)
        return self.get_payment_config().get("processing_fee_rate", 0.001)
    
    def get_execution_fee_rate(self) -> float:
        """Get execution fee rate for investments"""
        env_override = os.environ.get("TREASURY_EXECUTION_FEE_RATE")
        if env_override:
            return float(env_override)
        return self.get_investment_config().get("execution_fee_rate", 0.001)
    
    def get_default_currency(self) -> str:
        """Get default currency for payments"""
        env_override = os.environ.get("TREASURY_CURRENCY")
        if env_override:
            return env_override
        return self.get_payment_config().get("default_currency", "USDT")
    
    def get_min_threshold(self) -> float:
        """Get minimum recommendation threshold for investments"""
        env_override = os.environ.get("TREASURY_MIN_THRESHOLD")
        if env_override:
            return float(env_override)
        return self.get_investment_config().get("min_recommendation_threshold", 1000)
    
    def is_simulation_mode(self) -> bool:
        """Check if simulation mode is enabled"""
        return self.get_payment_config().get("simulation_mode", True)


# Global config instance
_config_instance = None

def get_config() -> TreasuryConfig:
    """Get global configuration instance (singleton)"""
    global _config_instance
    if _config_instance is None:
        _config_instance = TreasuryConfig()
    return _config_instance
