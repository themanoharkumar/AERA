"""AERA Evidence Management System package.

This package exposes evidence preservation layers, validates metadata schema values,
manages local/modular file storage layouts, and registers incident proof.
"""

from src.evidence.evidence import Evidence
from src.evidence.exceptions import EvidenceError, StorageError, ValidationError
from src.evidence.manager import EvidenceManager
from src.evidence.metadata import EvidenceMetadata
from src.evidence.storage import BaseStorage, LocalStorage
from src.evidence.validator import EvidenceValidator

__all__ = [
    "Evidence",
    "EvidenceManager",
    "BaseStorage",
    "LocalStorage",
    "EvidenceMetadata",
    "EvidenceValidator",
    "EvidenceError",
    "StorageError",
    "ValidationError",
]
