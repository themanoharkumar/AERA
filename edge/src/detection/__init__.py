"""AERA Detection Engine package.

This package exposes the core elements of the AI detection plugin system, including
abstract classes, detector registries, loaders, execution pipelines, and result models.
"""

from src.detection.detector import BaseDetector, BaseModel
from src.detection.exceptions import (
    DetectionError,
    InferenceError,
    ModelLoadError,
    PluginLoadError,
    PluginRegistryError,
)
from src.detection.fire.detector import FireDetector
from src.detection.loader import ModelLoader
from src.detection.pipeline import DetectionPipeline
from src.detection.registry import DetectorRegistry
from src.detection.result import DetectionResult
from src.detection.smoke.detector import SmokeDetector

__all__ = [
    "BaseDetector",
    "BaseModel",
    "DetectorRegistry",
    "ModelLoader",
    "DetectionPipeline",
    "DetectionResult",
    "DetectionError",
    "ModelLoadError",
    "InferenceError",
    "PluginRegistryError",
    "PluginLoadError",
    "FireDetector",
    "SmokeDetector",
]
