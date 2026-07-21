"""Simulated AI model implementation for smoke detection.

This module defines the HeuristicSmokeModel class, which simulates AI inference using BGR color-range heuristics.
"""

from typing import Any, Dict, List, Tuple
import numpy as np

from src.detection.detector import BaseModel


# TODO: In future versions, implement other concrete subclasses of BaseModel,
# such as YoloModel (PyTorch/Ultralytics), OnnxModel (ONNX Runtime), and TensorRTModel.
# These will support GPU acceleration, TensorRT optimization, and batch inference.
class HeuristicSmokeModel(BaseModel):
    """Simulated AI model for smoke detection using BGR color-range heuristics.

    This model runs heuristics on numpy frame arrays to identify potential grayish
    smoke pixel clusters (low variance across R, G, and B channels, and moderate brightness).
    """

    def __init__(self, model_path: str) -> None:
        """Initialize the SmokeModel instance.

        Args:
            model_path: Path to the model file or weights.
        """
        self.model_path = model_path
        self._released = False

    def predict(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Perform simulated inference on a frame.

        Analyzes the frame to identify grayish pixels (low color saturation and
        brightness in range [100, 200]). If a significant cluster is found,
        it yields a detection bounding box.

        Args:
            frame: NumPy array of shape (H, W, 3) in BGR format.

        Returns:
            A list of prediction dictionaries. If smoke is detected, each contains:
                - 'confidence': Float representing prediction confidence.
                - 'bounding_boxes': List of (xmin, ymin, xmax, ymax) tuples.
                - 'metadata': Dictionary containing custom metadata.

        Raises:
            RuntimeError: If predict is called after the model is released.
        """
        if self._released:
            raise RuntimeError("Cannot run predict() on a released model.")

        # Ensure frame is 3-channel BGR
        if frame.ndim != 3 or frame.shape[2] != 3:
            return []

        blue = frame[:, :, 0]
        green = frame[:, :, 1]
        red = frame[:, :, 2]

        # Gray pixels have low difference between R, G, B channels
        diff_rg = np.abs(red.astype(int) - green.astype(int))
        diff_gb = np.abs(green.astype(int) - blue.astype(int))
        diff_br = np.abs(blue.astype(int) - red.astype(int))

        # Brightness (average BGR value)
        brightness = (red.astype(int) + green.astype(int) + blue.astype(int)) // 3

        # Match grayish pixels with moderate brightness
        smoke_mask = (
            (diff_rg < 10)
            & (diff_gb < 10)
            & (diff_br < 10)
            & (brightness >= 100)
            & (brightness <= 200)
        )
        y_indices, x_indices = np.where(smoke_mask)

        # If we have a significant cluster of matching pixels
        if len(x_indices) > 50:
            xmin, xmax = int(np.min(x_indices)), int(np.max(x_indices))
            ymin, ymax = int(np.min(y_indices)), int(np.max(y_indices))

            # Scale confidence with cluster size up to 0.99
            confidence = min(0.50 + (len(x_indices) / 5000.0), 0.99)

            return [
                {
                    "confidence": confidence,
                    "bounding_boxes": [(xmin, ymin, xmax, ymax)],
                    "metadata": {
                        "pixel_count": len(x_indices),
                        "model_type": "heuristics_gray_threshold",
                        "model_path": self.model_path,
                    },
                }
            ]

        return []

    def release(self) -> None:
        """Release the model resources and mark as released."""
        self._released = True
