"""Thread-safe detector plugin registry for AERA.

This module defines the DetectorRegistry class, which stores and manages
the active detector plugin instances.
"""

import logging
import threading
from typing import Dict, List

from src.detection.detector import BaseDetector
from src.detection.exceptions import PluginRegistryError

logger = logging.getLogger(__name__)


class DetectorRegistry:
    """Thread-safe registry maintaining the collection of registered AI detector plugins.

    Other business modules and pipelines query this registry to fetch active detectors.
    """

    def __init__(self) -> None:
        """Initialize the DetectorRegistry with an empty collection."""
        self._detectors: Dict[str, BaseDetector] = {}
        self._lock = threading.Lock()

    def register_detector(self, name: str, detector: BaseDetector) -> None:
        """Register a detector instance under a unique name.

        Args:
            name: Unique name of the detector (e.g. 'fire_detector').
            detector: An instance of a detector class inheriting from BaseDetector.

        Raises:
            PluginRegistryError: If the name already exists or if the detector is invalid.
        """
        if not name:
            raise PluginRegistryError("Detector name cannot be empty.")
        if not isinstance(detector, BaseDetector):
            raise PluginRegistryError("Registered detector must inherit from BaseDetector.")

        with self._lock:
            if name in self._detectors:
                raise PluginRegistryError(f"Detector '{name}' is already registered.")
            self._detectors[name] = detector

        logger.info("Registered detector plugin: %s", name)

    def unregister_detector(self, name: str) -> None:
        """Unregister a detector instance.

        Args:
            name: The name of the detector plugin to remove.

        Raises:
            PluginRegistryError: If the detector name cannot be found.
        """
        with self._lock:
            if name not in self._detectors:
                raise PluginRegistryError(f"Detector '{name}' is not registered.")
            del self._detectors[name]

        logger.info("Unregistered detector plugin: %s", name)

    def get_detector(self, name: str) -> BaseDetector:
        """Retrieve a registered detector instance by its name.

        Args:
            name: The unique name of the detector plugin.

        Returns:
            The BaseDetector instance.

        Raises:
            PluginRegistryError: If the detector name cannot be found.
        """
        with self._lock:
            detector = self._detectors.get(name)
            if detector is None:
                raise PluginRegistryError(f"Detector '{name}' not found in registry.")
            return detector

    def list_detectors(self) -> List[str]:
        """List the names of all registered detectors.

        Returns:
            A list of detector name strings.
        """
        with self._lock:
            return list(self._detectors.keys())

    def clear(self) -> None:
        """Clear all registered detectors from the registry."""
        with self._lock:
            self._detectors.clear()
        logger.info("Cleared detector registry.")
