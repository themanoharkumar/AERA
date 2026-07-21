"""Plugin registry for AERA detectors."""

from __future__ import annotations

from typing import Dict, List


class PluginRegistry:
    """Simple registry for available detectors."""

    def __init__(self) -> None:
        self._plugins: Dict[str, str] = {}

    def register(self, name: str, module_path: str) -> None:
        self._plugins[name] = module_path

    def list_plugins(self) -> List[str]:
        return sorted(self._plugins)

    def get_plugin(self, name: str) -> str:
        return self._plugins[name]
