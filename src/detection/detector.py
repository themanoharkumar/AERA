"""Abstract base detector interface for AERA Detection Engine.

This module defines the BaseDetector ABC which all concrete detector plugins
must implement to ensure unified lifecycle and inference APIs.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
import numpy as np

from src.detection.result import DetectionResult


class BaseModel(ABC):
    """Abstract base class representing an AI model for emergency detection.

    Concrete model implementations (e.g. Heuristic models, ONNX, PyTorch, YOLO)
    must inherit from BaseModel and implement predict and release methods.
    """

    @abstractmethod
    def predict(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Perform inference on the input frame.

        Args:
            frame: A NumPy array representing the video frame (typically BGR format).

        Returns:
            A list of raw prediction dictionaries containing confidence,
            bounding boxes, and extra metadata.
        """
        pass

    @abstractmethod
    def release(self) -> None:
        """Release any loaded weights and resources from CPU/GPU memory."""
        pass


class BaseDetector(ABC):
    """Abstract base class defining the interface for AERA AI detector plugins.

    Every concrete detector plugin must inherit from this class and implement
    all abstract methods to load models, execute inference, and release resources.
    """

    @abstractmethod
    def load_model(self) -> None:
        """Load the AI model files, weights, and configurations.

        Raises:
            ModelLoadError: If loading the model files fails.
        """
        pass

    @abstractmethod
    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """Perform AI model inference on the provided video frame.

        Args:
            frame: A NumPy array representing the video frame (typically BGR format).

        Returns:
            A list of DetectionResult objects containing detected objects.

        Raises:
            InferenceError: If frame preprocessing or model prediction fails.
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Release all model resources, GPU memory, and clear cache."""
        pass
