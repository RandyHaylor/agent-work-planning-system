"""document_extraction: bytes + metadata in, citable text out. No network, no database.

Public surface only (spec 05-spec-document-extraction.md).
"""
from planning_system.document_extraction.document_extractor import build_document_extractor
from planning_system.document_extraction.extraction_interface import DocumentExtractor
from planning_system.document_extraction.extraction_types import (
    AttemptRecord, ExtractionFailed, ExtractionInput, ExtractionResult, SourceDocument, StrategyFailed,
    StrategyOutput, TextKind, UnknownStrategy,
)
from planning_system.document_extraction.strategies import ExtractionStrategy

__all__ = [
    "DocumentExtractor", "build_document_extractor", "ExtractionStrategy",
    "AttemptRecord", "ExtractionFailed", "ExtractionInput", "ExtractionResult", "SourceDocument",
    "StrategyFailed", "StrategyOutput", "TextKind", "UnknownStrategy",
]
