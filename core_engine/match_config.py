"""
Match Simulation Configuration — externalized constant loader.

Reads match simulation parameters from an optional JSON configuration file
(``match_profiles.json`` at the project root or path given by the
``MATCH_PROFILES_PATH`` env var).  If the file doesn't exist, all values
fall back to the defaults in :mod:`core_engine.match_constants`.

Profiles allow game designers to tweak simulation feel without code changes:

.. code-block:: json

    {
      "profiles": {
        "realistic": {
          "FINISHER_DAMAGE": 25,
          "BOTCH_MAX_CHANCE": 0.12,
          "NEAR_FALL_CHANCE": 0.20
        },
        "arcade": {
          "FINISHER_DAMAGE": 15,
          "NEAR_FALL_CHANCE": 0.35,
          "FINISH_BASE_CHANCE": 0.4
        },
        "storyline_heavy": {
          "INTERFERENCE_MAX_CHANCE": 0.50,
          "SHOOT_MAX_CHANCE": 0.10
        }
      },
      "active_profile": "realistic"
    }

Usage::

    from core_engine.match_config import get_match_config
    cfg = get_match_config()            # uses active profile
    cfg = get_match_config("arcade")    # explicit profile

    # Access values as attributes:
    damage = cfg.FINISHER_DAMAGE
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

import core_engine.match_constants as _defaults

logger = logging.getLogger(__name__)

_CONFIG_PATH = os.getenv(
    "MATCH_PROFILES_PATH",
    str(Path(__file__).resolve().parent.parent / "match_profiles.json"),
)

# Loaded profiles cache (populated on first access)
_profiles: Optional[Dict[str, Dict[str, Any]]] = None
_active_profile_name: Optional[str] = None


def _load_profiles() -> None:
    global _profiles, _active_profile_name
    _profiles = {}
    _active_profile_name = None

    if not os.path.isfile(_CONFIG_PATH):
        logger.debug(
            "No match_profiles.json found at %s — using defaults", _CONFIG_PATH
        )
        return

    try:
        with open(_CONFIG_PATH) as f:
            data = json.load(f)
        _profiles = data.get("profiles", {})
        _active_profile_name = data.get("active_profile")
        logger.info(
            "Loaded %d match profile(s) from %s (active=%s)",
            len(_profiles),
            _CONFIG_PATH,
            _active_profile_name,
        )
    except Exception as e:
        logger.warning("Failed to load match_profiles.json: %s — using defaults", e)


class MatchConfig:
    """Read-only namespace that overlays profile overrides on top of
    :mod:`core_engine.match_constants` defaults."""

    def __init__(self, overrides: Dict[str, Any]):
        self._overrides = overrides

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        if name in self._overrides:
            return self._overrides[name]
        val = getattr(_defaults, name, None)
        if val is None:
            raise AttributeError(f"Unknown match constant: {name}")
        return val

    def as_dict(self) -> Dict[str, Any]:
        """Return all constants (defaults merged with profile overrides)."""
        result = {
            k: v
            for k, v in vars(_defaults).items()
            if k.isupper() and not k.startswith("_")
        }
        result.update(self._overrides)
        return result


# Default config with no overrides (matches existing behaviour exactly)
_DEFAULT_CONFIG = MatchConfig({})


def get_match_config(profile_name: Optional[str] = None) -> MatchConfig:
    """Return a :class:`MatchConfig` for the given profile.

    * ``None`` → active profile from the config file (or bare defaults).
    * Explicit name → that profile's overrides.
    """
    if _profiles is None:
        _load_profiles()

    name = profile_name or _active_profile_name
    if not name or not _profiles or name not in _profiles:
        return _DEFAULT_CONFIG

    return MatchConfig(_profiles[name])


def list_profiles() -> Dict[str, Dict[str, Any]]:
    """Return all available profile names and their overrides."""
    if _profiles is None:
        _load_profiles()
    return dict(_profiles or {})


def reload_profiles() -> None:
    """Force-reload profiles from disk (e.g. after a config edit)."""
    global _profiles
    _profiles = None
    _load_profiles()
