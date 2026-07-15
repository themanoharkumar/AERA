"""Fire detector plugin implementation for AERA.

This module defines the FireDetector class which inherits from BaseDetector
and performs fire detection inference using a HeuristicFireModel.
"""

import time
from typing import Any, List, Optional
import uuid
import numpy as np

from src.detection.detector import BaseDetector
from src.detection.exceptions import InferenceError, ModelLoadError
from src.detection.loader import ModelLoader
from src.detection.result import DetectionResult


class FireDetector(BaseDetector):
    """Fire detector plugin analyzing video frames for fire presence."""

    def __init__(
        self,
        model_path: str = "models/fire_yolov8.pt",
        confidence_threshold: float = 0.5,
        model_loader: Optional[ModelLoader] = None,
    ) -> None:
        """Initialize the FireDetector.

        Args:
            model_path: Path to the fire detection model weights.
            confidence_threshold: Confidence threshold for predictions.
            model_loader: Optional ModelLoader instance for cached loading.
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.model_loader = model_loader if model_loader is not None else ModelLoader()
        self.model: Any = None

    def load_model(self) -> None:
        """Load the fire detection model weights via the ModelLoader.

        Raises:
            ModelLoadError: If loading fails.
        """
        try:
            from src.detection.fire.model import HeuristicFireModel

            # Use model_loader to load/cache the HeuristicFireModel
            # TODO: In future versions, this can be swapped with a real YOLOv8/ONNX model loader hook.
            self.model = self.model_loader.load_model(
                model_path=self.model_path,
                model_type="fire",
                load_fn=lambda path: HeuristicFireModel(path),
            )
        except Exception as e:
            raise ModelLoadError(f"Failed to load fire detection model: {e}") from e

    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        """Perform fire detection inference on the frame.

        Args:
            frame: A NumPy array representing the video frame.

        Returns:
            A list of DetectionResult objects.

        Raises:
            InferenceError: If inference fails or model is not loaded.
        """
        if self.model is None:
            raise InferenceError("Model not loaded. Call load_model() first.")
        if frame is None or not isinstance(frame, np.ndarray):
            raise InferenceError("Invalid frame input: Must be a NumPy array.")

        start_time = time.time()
        try:
            # Delegate inference to the FireModel
            raw_predictions = self.model.predict(frame)
            inference_time = time.time() - start_time

            results: List[DetectionResult] = []
            for pred in raw_predictions:
                conf = pred.get("confidence", 0.0)
                if conf >= self.confidence_threshold:
                    results.append(
                        DetectionResult(
                            detection_id=str(uuid.uuid4()),
                            detector_name="fire_detector",
                            label="fire",
                            confidence=conf,
                            timestamp=time.time(),
                            inference_time=inference_time,
                            bounding_boxes=pred.get("bounding_boxes", []),
                            metadata=pred.get("metadata", {}),
                        )
                    )
            return results
        except Exception as e:
            raise InferenceError(f"Inference failed in FireDetector: {e}") from e

    def shutdown(self) -> None:
        """Release the model weights and clear the reference."""
        if self.model is not None:
            self.model_loader.release_model(self.model_path)
            self.model = None
