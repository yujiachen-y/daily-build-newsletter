"""Article ingest module."""

from .ingest import Ingestor
from .store import Store

__all__ = ["Store", "Ingestor"]
