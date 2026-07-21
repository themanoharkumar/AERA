"""Detection pipeline coordination for AERA.

This module defines the DetectionPipeline class, which passes incoming camera frames
through registered AI detector plugins and aggregates their raw DetectionResults.
"""

import logging
from typing import List, Optional
import numpy as np

from src.detection.exceptions import InferenceError
from src.detection.registry import DetectorRegistry
from src.detection.result import DetectionResult

logger = logging.getLogger(__name__)


class DetectionPipeline:
    """Coordinates frame inference across active detector plugins.

    The pipeline retrieves active detectors from a registry, runs them
    on input frames, aggregates their results, and returns them to the caller.

    # TODO: Future versions can implement:
    # 1. Parallel Inference: Run detectors concurrently via a thread pool or async/io loop.
    # 2. Batch Inference: Support batched frame execution for high-throughput GPU pipelining.
    # 3. Non-blocking/Asynchronous stream processing with queue-based ingestion.
    """

    def __init__(self, registry: DetectorRegistry) -> None:
        """Initialize the pipeline with a detector registry.

        Args:
            registry: The DetectorRegistry containing registered detector plugins.
        """
        self.registry = registry

    def process_frame(
        self,
        frame: np.ndarray,
        detector_names: Optional[List[str]] = None,
    ) -> List[DetectionResult]:
        """Process a video frame through active detector plugins.

        Runs inference using either all registered detectors or a specified subset.

        Args:
            frame: A NumPy array representing the video frame.
            detector_names: Optional list of detector names to execute. If None,
                executes all registered detectors.

        Returns:
            A list of accumulated DetectionResult objects.

        Raises:
            InferenceError: If processing fails in any detector.
        """
        if frame is None or not isinstance(frame, np.ndarray):
            raise InferenceError("Invalid frame input: Must be a NumPy array.")

        results: List[DetectionResult] = []
        target_detectors = detector_names if detector_names is not None else self.registry.list_detectors()

        for name in target_detectors:
            try:
                detector = self.registry.get_detector(name)
                detector_results = detector.detect(frame)
                results.extend(detector_results)
            except Exception as e:
                logger.exception("Error running detector '%s' on frame", name)
                raise InferenceError(f"Detector '{name}' failed during frame inference: {e}") from e

        return results
