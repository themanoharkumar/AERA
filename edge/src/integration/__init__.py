"""AERA System Integration package.

This package connects and orchestrates AERA backend subsystems into a unified,
thread-safe emergency processing pipeline.
"""

from src.integration.coordinator import SystemCoordinator
from src.integration.exceptions import (
    IntegrationError,
    PipelineError,
    ValidationError,
)
from src.integration.health import SystemHealthMonitor
from src.integration.pipeline import EmergencyPipeline
from src.integration.validator import SystemValidator

__all__ = [
    "SystemCoordinator",
    "EmergencyPipeline",
    "SystemValidator",
    "SystemHealthMonitor",
    "IntegrationError",
    "PipelineError",
    "ValidationError",
]
