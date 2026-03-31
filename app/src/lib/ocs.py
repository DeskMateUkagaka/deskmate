from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx

_OCS_URL = "https://api.pling.com/ocs/v1/content/data"
_STORE_SEARCH_TAG = "deskmate"
_SUPPORTED_VERSION_TAG = "deskmate-v1"


@dataclass
class OcsContentItem:
    id: str
    name: str
    version: str
    personid: str
    downloads: int
    score: int
    summary: str
    description: str
    previewpic1: str
    smallpreviewpic1: str
    detailpage: str
    tags: str
    downloadlink1: str
    downloadname1: str
    downloadsize1: int
    downloadmd5sum1: str


@dataclass
class OcsBrowseResult:
    totalitems: int
    itemsperpage: int
    data: list[OcsContentItem]


def _to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    return int(value)


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _split_tags(tags: str) -> set[str]:
    return {tag.strip().lower() for tag in tags.split(",") if tag.strip()}


def _matches_store_tags(item: OcsContentItem) -> bool:
    tags = _split_tags(item.tags)
    return _STORE_SEARCH_TAG in tags and _SUPPORTED_VERSION_TAG in tags


def _matches_search(item: OcsContentItem, search: str) -> bool:
    if not search:
        return True
    haystacks = [item.name, item.summary, item.description, item.personid, item.tags]
    search_lower = search.lower()
    return any(search_lower in value.lower() for value in haystacks if value)


def browse_skins(
    *,
    search: str = "",
    sortmode: str = "new",
    page: int = 0,
    pagesize: int = 20,
) -> OcsBrowseResult:
    with httpx.Client(timeout=20.0, follow_redirects=True) as client:
        params = {
            "format": "json",
            "search": _STORE_SEARCH_TAG,
            "sortmode": sortmode,
            "page": page,
            "pagesize": pagesize,
        }
        response = client.get(
            _OCS_URL,
            params=params,
        )
        response.raise_for_status()
        payload = response.json()

    items = [
        OcsContentItem(
            id=_to_str(item.get("id")),
            name=_to_str(item.get("name")),
            version=_to_str(item.get("version")),
            personid=_to_str(item.get("personid")),
            downloads=_to_int(item.get("downloads")),
            score=_to_int(item.get("score")),
            summary=_to_str(item.get("summary")),
            description=_to_str(item.get("description")),
            previewpic1=_to_str(item.get("previewpic1")),
            smallpreviewpic1=_to_str(item.get("smallpreviewpic1")),
            detailpage=_to_str(item.get("detailpage")),
            tags=_to_str(item.get("tags")),
            downloadlink1=_to_str(item.get("downloadlink1")),
            downloadname1=_to_str(item.get("downloadname1")),
            downloadsize1=_to_int(item.get("downloadsize1")),
            downloadmd5sum1=_to_str(item.get("downloadmd5sum1")),
        )
        for item in payload.get("data", [])
    ]

    filtered_items = [
        item for item in items if _matches_store_tags(item) and _matches_search(item, search)
    ]

    return OcsBrowseResult(
        totalitems=len(filtered_items),
        itemsperpage=len(filtered_items),
        data=filtered_items,
    )


def download_skin_zip(
    download_url: str,
    destination: Path,
    progress: Callable[[int, int | None], None] | None = None,
) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with httpx.stream("GET", download_url, timeout=60.0, follow_redirects=True) as response:
        response.raise_for_status()
        total_header = response.headers.get("content-length")
        total = int(total_header) if total_header else None
        downloaded = 0
        with destination.open("wb") as fh:
            for chunk in response.iter_bytes():
                if not chunk:
                    continue
                fh.write(chunk)
                downloaded += len(chunk)
                if progress is not None:
                    progress(downloaded, total)
    return destination
