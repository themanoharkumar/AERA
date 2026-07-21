"""AI model caching loader for AERA.

This module defines the ModelLoader class, which caches loaded AI model instances
to avoid redundant loading overhead.
"""

import logging
import threading
from typing import Any, Callable, Dict, Optional

from src.detection.exceptions import ModelLoadError

logger = logging.getLogger(__name__)


class ModelLoader:
    """Handles loading, caching, and releasing of AI model objects.

    Prevents loading the same model weights multiple times by maintaining
    an in-memory cache of loaded models.

    # TODO: Future versions can implement:
    # 1. Model Hot Swapping: Dynamic model version updates without pipeline restarts.
    # 2. VRAM/GPU Memory Management: Automatic eviction policy (e.g. LRU) when memory limit is hit.
    # 3. Dedicated ONNX Runtime and TensorRT engine backends.
    """

    def __init__(self) -> None:
        """Initialize the ModelLoader with an empty cache."""
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()

    def load_model(
        self,
        model_path: str,
        model_type: str,
        load_fn: Optional[Callable[..., Any]] = None,
        **kwargs: Any,
    ) -> Any:
        """Load and cache an AI model.

        If the model is already in the cache, returns the cached instance.
        Otherwise, uses the load_fn (or a default loading mechanism) to load it.

        Args:
            model_path: File system path or identifier of the model weights/config.
            model_type: Type of model (e.g. 'yolov8', 'custom').
            load_fn: Optional custom callable to load the model. If provided,
                it will be called as load_fn(model_path, **kwargs).
            **kwargs: Extra arguments passed to the load_fn.

        Returns:
            The loaded model instance.

        Raises:
            ModelLoadError: If loading fails or model_path is invalid.
        """
        if not model_path:
            raise ModelLoadError("Model path/identifier cannot be empty.")

        with self._lock:
            if model_path in self._cache:
                logger.debug("Model cache hit for: %s", model_path)
                return self._cache[model_path]

            logger.info("Model cache miss. Loading model from: %s", model_path)
            try:
                if load_fn is not None:
                    model = load_fn(model_path, **kwargs)
                else:
                    # Default placeholder loader if no function is provided
                    # In a real environment, this might check model_type and load via PyTorch/Ultralytics
                    model = f"MockModel({model_type}, path={model_path})"

                self._cache[model_path] = model
                return model
            except Exception as e:
                logger.exception("Failed to load model from %s", model_path)
                raise ModelLoadError(f"Error loading model from {model_path}: {e}")

    def get_model(self, model_path: str) -> Optional[Any]:
        """Get a model from cache if it exists, without triggering a load.

        Args:
            model_path: The model identifier/path.

        Returns:
            The model instance, or None if not cached.
        """
        with self._lock:
            return self._cache.get(model_path)

    def release_model(self, model_path: str) -> None:
        """Release a cached model and remove it from the cache.

        Args:
            model_path: The model identifier/path.
        """
        with self._lock:
            if model_path in self._cache:
                model = self._cache[model_path]
                if hasattr(model, "release"):
                    try:
                        model.release()
                    except Exception as e:
                        logger.error("Error calling release() on model: %s", e)
                elif hasattr(model, "close"):
                    try:
                        model.close()
                    except Exception as e:
                        logger.error("Error calling close() on model: %s", e)

                del self._cache[model_path]
                logger.info("Released model from cache: %s", model_path)

    def clear(self) -> None:
        """Release and clear all cached models."""
        with self._lock:
            keys = list(self._cache.keys())
        for key in keys:
            self.release_model(key)
        logger.info("Cleared all model caches.")
