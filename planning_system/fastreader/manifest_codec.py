"""Manifest <-> JSON-able dict (the rebuild logic formerly in cache.load_manifest), no files."""
from dataclasses import asdict
from typing import Any, Dict, List

from planning_system.fastreader.models import Manifest, Marker


def manifest_to_dict(manifest: Manifest) -> Dict[str, Any]:
    return asdict(manifest)


def manifest_from_dict(data: Dict[str, Any]) -> Manifest:
    markers: Dict[str, List[Marker]] = {}
    for m_type, m_list in data['markers'].items():
        markers[m_type] = [Marker(**m_data) for m_data in m_list]
    return Manifest(
        source=data['source'],
        total_chars=data['total_chars'],
        total_lines=data['total_lines'],
        markers=markers,
    )
