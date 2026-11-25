from __future__ import annotations

from planning_system.document_extraction.content_type_detection.file_name_hint import media_type_from_file_name
from planning_system.document_extraction.content_type_detection.header_content_type import media_type_from_header
from planning_system.document_extraction.content_type_detection.leading_bytes_sniffer import sniff_media_type
from planning_system.document_extraction.extraction_interface import ContentTypeDetector

UNKNOWN_CONTENT_TYPE = "application/octet-stream"


class LayeredContentTypeDetector(ContentTypeDetector):
    def detect(self, raw_bytes: bytes, content_type_header: str | None, file_name: str | None) -> str:
        return (sniff_media_type(raw_bytes)
                or media_type_from_header(content_type_header)
                or media_type_from_file_name(file_name)
                or UNKNOWN_CONTENT_TYPE)
