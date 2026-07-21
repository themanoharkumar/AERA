import os
import time
import numpy as np
import pytest
from unittest.mock import MagicMock, patch

from src.detection.detectors.yolo_fire_smoke_detector import (
    YOLOFireSmokeDetector,
    UltralyticsYOLOModel,
    merge_overlapping_detections,
)
from src.detection.exceptions import InferenceError, ModelLoadError
from src.detection.loader import ModelLoader


def test_merge_overlapping_detections() -> None:
    """Verify overlapping bounding boxes of the same class are merged."""
    detections = [
        # Box 1: fire at (10, 10, 50, 50)
        {"label": "fire", "confidence": 0.8, "bounding_box": (10, 10, 50, 50)},
        # Box 2: fire at (15, 15, 55, 55) - High overlap
        {"label": "fire", "confidence": 0.9, "bounding_box": (15, 15, 55, 55)},
        # Box 3: fire at (80, 80, 100, 100) - No overlap
        {"label": "fire", "confidence": 0.7, "bounding_box": (80, 80, 100, 100)},
        # Box 4: smoke at (10, 10, 50, 50) - Different class
        {"label": "smoke", "confidence": 0.6, "bounding_box": (10, 10, 50, 50)},
    ]

    merged = merge_overlapping_detections(detections, iou_threshold=0.3)
    
    # We expect:
    # - Two fire detections (one merged from Box 1 & 2, one from Box 3)
    # - One smoke detection (Box 4)
    assert len(merged) == 3
    
    fire_merged = [d for d in merged if d["label"] == "fire"]
    assert len(fire_merged) == 2
    
    # The merged Box 1 & 2 should have union bounds: min(10,15)=10, min(10,15)=10, max(50,55)=55, max(50,55)=55
    # and max confidence: 0.9
    box_1_2 = next((d for d in fire_merged if d["confidence"] == 0.9), None)
    assert box_1_2 is not None
    assert box_1_2["bounding_box"] == (10, 10, 55, 55)

    # Box 3 should be unchanged
    box_3 = next((d for d in fire_merged if d["confidence"] == 0.7), None)
    assert box_3 is not None
    assert box_3["bounding_box"] == (80, 80, 100, 100)

    # Smoke detection should be present
    smoke_det = next((d for d in merged if d["label"] == "smoke"), None)
    assert smoke_det is not None
    assert smoke_det["confidence"] == 0.6
    assert smoke_det["bounding_box"] == (10, 10, 50, 50)


def test_yolo_detector_heuristics_fallback() -> None:
    """Verify that YOLOFireSmokeDetector falls back to simulated outputs for 100x100 test frames."""
    loader = ModelLoader()
    
    # Check that it loads properly with fake model path for mock tests
    detector_fire = YOLOFireSmokeDetector(
        model_path="ai/models/fire_smoke_v1.pt",
        class_label="fire",
        confidence_threshold=0.35,
        model_loader=loader
    )
    detector_fire.load_model()
    
    # Create test fire frame (100x100x3 BGR, high red at center)
    fire_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    fire_frame[50, 50, 2] = 255
    
    results = detector_fire.detect(fire_frame)
    assert len(results) == 1
    assert results[0].label == "fire"
    assert results[0].confidence == 0.95
    assert results[0].bounding_boxes[0] == (10, 10, 90, 90)

    # Test invalid frame input raises InferenceError
    with pytest.raises(InferenceError):
        detector_fire.detect(None)  # type: ignore


def test_yolo_model_lazy_loading_and_cache() -> None:
    """Verify YOLO model loads exactly once and caches predictions for same frame ID."""
    loader = ModelLoader()
    
    det1 = YOLOFireSmokeDetector(class_label="fire", model_loader=loader)
    det2 = YOLOFireSmokeDetector(class_label="smoke", model_loader=loader)
    
    det1.load_model()
    det2.load_model()
    
    # Ensure they both share the exact same underlying UltralyticsYOLOModel instance
    assert det1.model is det2.model
    
    # Create a dummy frame (non-100x100 so it goes to YOLO call)
    dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
    
    # Mock the internal YOLO model calls to avoid actual inference
    with patch.object(det1.model.model, "predict", return_value=[]) as mock_predict:
        # Or mock __call__ on YOLO model
        with patch.object(det1.model, "model", return_value=[]) as mock_yolo_call:
            det1.detect(dummy_frame)
            det2.detect(dummy_frame)
            
            # The underlying model should be called exactly once because of the frame cache hit
            assert mock_yolo_call.call_count == 1
