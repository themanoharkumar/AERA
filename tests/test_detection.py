"""Unit tests for the AERA Detection Engine.

This module contains test cases for exceptions, DetectionResult, BaseDetector,
DetectorRegistry, ModelLoader, DetectionPipeline, FireDetector, and SmokeDetector.
"""

import time
import concurrent.futures
from typing import List
import numpy as np
import pytest

from src.detection import (
    BaseDetector,
    BaseModel,
    DetectorRegistry,
    ModelLoader,
    DetectionPipeline,
    DetectionResult,
    DetectionError,
    ModelLoadError,
    InferenceError,
    PluginRegistryError,
    PluginLoadError,
    FireDetector,
    SmokeDetector,
)


# ==============================================================================
# 1. Test Custom Exceptions
# ==============================================================================
def test_exceptions_hierarchy() -> None:
    """Verify exceptions inherit from DetectionError and support custom messages."""
    assert issubclass(ModelLoadError, DetectionError)
    assert issubclass(InferenceError, DetectionError)
    assert issubclass(PluginRegistryError, DetectionError)
    assert issubclass(PluginLoadError, DetectionError)

    exc = ModelLoadError("Custom load error")
    assert str(exc) == "Custom load error"
    assert exc.message == "Custom load error"


# ==============================================================================
# 2. Test DetectionResult
# ==============================================================================
def test_detection_result_initialization() -> None:
    """Verify DetectionResult initializes with correct values and default lists/dicts."""
    res = DetectionResult(
        detection_id="det_01",
        detector_name="test_detector",
        label="person",
        confidence=0.88,
        timestamp=1719876543.21,
        inference_time=0.015,
        bounding_boxes=[(10, 20, 100, 200)],
        metadata={"version": "1.0"},
    )

    assert res.detection_id == "det_01"
    assert res.detector_name == "test_detector"
    assert res.label == "person"
    assert res.confidence == 0.88
    assert res.timestamp == 1719876543.21
    assert res.inference_time == 0.015
    assert res.bounding_boxes == [(10, 20, 100, 200)]
    assert res.metadata == {"version": "1.0"}

    # Check repr
    rep = repr(res)
    assert "det_01" in rep
    assert "test_detector" in rep
    assert "person" in rep
    assert "0.88" in rep


# ==============================================================================
# 3. Test BaseDetector ABC Constraints
# ==============================================================================
def test_base_detector_abc() -> None:
    """Verify BaseDetector cannot be instantiated directly and concrete subclassing is enforced."""
    with pytest.raises(TypeError):
        BaseDetector()  # type: ignore

    class BuggyDetector(BaseDetector):
        pass

    with pytest.raises(TypeError):
        BuggyDetector()  # type: ignore


def test_base_model_abc() -> None:
    """Verify BaseModel cannot be instantiated directly and concrete subclassing is enforced."""
    with pytest.raises(TypeError):
        BaseModel()  # type: ignore

    class BuggyModel(BaseModel):
        pass

    with pytest.raises(TypeError):
        BuggyModel()  # type: ignore



# ==============================================================================
# 4. Test DetectorRegistry
# ==============================================================================
class MockDetector(BaseDetector):
    """Simple mock detector for testing registry and pipeline."""
    def __init__(self) -> None:
        self.loaded = False
        self.shutdown_called = False

    def load_model(self) -> None:
        self.loaded = True

    def detect(self, frame: np.ndarray) -> List[DetectionResult]:
        return [
            DetectionResult(
                detection_id="mock_id",
                detector_name="mock_detector",
                label="mock_label",
                confidence=0.99,
                timestamp=time.time(),
                inference_time=0.001,
            )
        ]

    def shutdown(self) -> None:
        self.shutdown_called = True


def test_detector_registry() -> None:
    """Verify DetectorRegistry performs thread-safe registrations and validation checks."""
    registry = DetectorRegistry()
    detector = MockDetector()

    # Register detector
    registry.register_detector("mock_det", detector)
    assert registry.get_detector("mock_det") is detector
    assert "mock_det" in registry.list_detectors()

    # Register duplicate raises PluginRegistryError
    with pytest.raises(PluginRegistryError):
        registry.register_detector("mock_det", detector)

    # Register invalid detector raises PluginRegistryError
    with pytest.raises(PluginRegistryError):
        registry.register_detector("invalid_det", "NotADetectorObject")  # type: ignore

    # Unregister detector
    registry.unregister_detector("mock_det")
    assert "mock_det" not in registry.list_detectors()

    # Unregister non-existent raises PluginRegistryError
    with pytest.raises(PluginRegistryError):
        registry.unregister_detector("non_existent")


# ==============================================================================
# 5. Test ModelLoader
# ==============================================================================
class SimpleModel(BaseModel):
    """Model with release tracking."""
    def __init__(self) -> None:
        self.released = False

    def predict(self, frame: np.ndarray) -> List[dict]:
        return []

    def release(self) -> None:
        self.released = True



def test_model_loader() -> None:
    """Verify ModelLoader handles caching, loads, and memory releases."""
    loader = ModelLoader()
    load_count = 0

    def mock_loader_fn(path: str) -> SimpleModel:
        nonlocal load_count
        load_count += 1
        return SimpleModel()

    # Initial load (miss)
    model1 = loader.load_model("model_A.pt", "custom", mock_loader_fn)
    assert load_count == 1
    assert model1 is not None

    # Secondary load (hit)
    model2 = loader.load_model("model_A.pt", "custom", mock_loader_fn)
    assert load_count == 1
    assert model2 is model1

    # Load with invalid path raises ModelLoadError
    with pytest.raises(ModelLoadError):
        loader.load_model("", "custom")

    # Release model
    loader.release_model("model_A.pt")
    assert model1.released is True
    assert loader.get_model("model_A.pt") is None

    # Load again after release (miss)
    model3 = loader.load_model("model_A.pt", "custom", mock_loader_fn)
    assert load_count == 2
    assert model3 is not model1


# ==============================================================================
# 6. Test DetectionPipeline
# ==============================================================================
def test_detection_pipeline() -> None:
    """Verify DetectionPipeline routes frames, aggregates results, and validates parameters."""
    registry = DetectorRegistry()
    detector = MockDetector()
    detector.load_model()
    registry.register_detector("mock_det", detector)

    pipeline = DetectionPipeline(registry)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Process frame
    results = pipeline.process_frame(frame)
    assert len(results) == 1
    assert results[0].detector_name == "mock_detector"
    assert results[0].label == "mock_label"

    # Processing invalid frame type raises InferenceError
    with pytest.raises(InferenceError):
        pipeline.process_frame("NotAFrame")  # type: ignore

    # Process with non-existent detector name in list raises InferenceError
    with pytest.raises(InferenceError):
        pipeline.process_frame(frame, ["non_existent"])


# ==============================================================================
# 7. Test Concrete Detectors (Fire & Smoke) Heuristics
# ==============================================================================
def test_concrete_fire_and_smoke_detectors() -> None:
    """Verify FireDetector and SmokeDetector scan frames and return detections based on heuristics."""
    loader = ModelLoader()

    # Instantiating detectors
    fire_det = FireDetector(model_path="fire_weights.pt", confidence_threshold=0.5, model_loader=loader)
    smoke_det = SmokeDetector(model_path="smoke_weights.pt", confidence_threshold=0.5, model_loader=loader)

    # Calling detect before load_model raises InferenceError
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.raises(InferenceError):
        fire_det.detect(frame)

    # Load models
    fire_det.load_model()
    smoke_det.load_model()

    # 1. Blank Frame test (no detections)
    blank_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert len(fire_det.detect(blank_frame)) == 0
    assert len(smoke_det.detect(blank_frame)) == 0

    # 2. Fire Frame test (large red square in BGR format: B=0, G=0, R=255)
    fire_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Paint a red square in the middle (row 20 to 80, col 20 to 80)
    fire_frame[20:80, 20:80, 2] = 255  # Red channel
    fire_frame[20:80, 20:80, 0] = 0    # Blue channel
    fire_frame[20:80, 20:80, 1] = 0    # Green channel

    fire_results = fire_det.detect(fire_frame)
    assert len(fire_results) == 1
    assert fire_results[0].detector_name == "fire_detector"
    assert fire_results[0].label == "fire"
    assert fire_results[0].confidence >= 0.5
    # The bounding box coordinates should surround the red square
    xmin, ymin, xmax, ymax = fire_results[0].bounding_boxes[0]
    assert xmin == 20
    assert ymin == 20
    assert xmax == 79
    assert ymax == 79

    # 3. Smoke Frame test (gray square in BGR: B=128, G=128, R=128)
    smoke_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Paint a grayish square in the middle (row 20 to 80, col 20 to 80)
    smoke_frame[20:80, 20:80, 0] = 128
    smoke_frame[20:80, 20:80, 1] = 128
    smoke_frame[20:80, 20:80, 2] = 128

    smoke_results = smoke_det.detect(smoke_frame)
    assert len(smoke_results) == 1
    assert smoke_results[0].detector_name == "smoke_detector"
    assert smoke_results[0].label == "smoke"
    assert smoke_results[0].confidence >= 0.5
    xmin, ymin, xmax, ymax = smoke_results[0].bounding_boxes[0]
    assert xmin == 20
    assert ymin == 20
    assert xmax == 79
    assert ymax == 79

    # Teardown
    fire_det.shutdown()
    smoke_det.shutdown()

    assert fire_det.model is None
    assert smoke_det.model is None


def test_heuristic_models_direct() -> None:
    """Verify HeuristicFireModel and HeuristicSmokeModel release lifecycle and error states."""
    from src.detection.fire.model import HeuristicFireModel
    from src.detection.smoke.model import HeuristicSmokeModel

    fire_m = HeuristicFireModel("dummy_fire.pt")
    smoke_m = HeuristicSmokeModel("dummy_smoke.pt")

    # Release models
    fire_m.release()
    smoke_m.release()

    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Calling predict after release raises RuntimeError
    with pytest.raises(RuntimeError):
        fire_m.predict(frame)

    with pytest.raises(RuntimeError):
        smoke_m.predict(frame)

