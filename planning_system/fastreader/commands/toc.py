from typing import List, Dict, Any, Optional, Union
from planning_system.fastreader.cache import as_reader_cache
from planning_system.fastreader.reader_cache_port import ReaderCachePort
from planning_system.fastreader.toc_cli import build_toc

def run_toc(
    manifest_hash: str,
    cache: Union[ReaderCachePort, str],
    marker_types: Optional[List[str]] = None,
    preview_length: int = 30,
    limit: Optional[int] = 15,
    end_preview_length: int = 0,
) -> List[Dict[str, Any]]:
    """Execute the toc command logic.
    
    1. Load manifest from <hash>.json
    2. Load content lines from <hash>.txt
    3. Build and return TOC
    """
    item = as_reader_cache(cache).get(manifest_hash)
    
    return build_toc(
        item.manifest,
        item.lines,
        marker_types=marker_types,
        preview_length=preview_length,
        limit=limit,
        end_preview_length=end_preview_length,
    )
