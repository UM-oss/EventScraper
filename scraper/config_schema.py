"""
Pydantic shema za validacijo YAML konfiguracij virov in medijev.
Pokliče se ob startupu — napačna konfiguracija → jasna napaka.
"""

import os
from typing import List, Optional, Dict, ClassVar, Set
import yaml

from pydantic import BaseModel, Field, field_validator, ValidationError


# =====================================================================
# VIRI
# =====================================================================

class SourcePagination(BaseModel):
    type: str = "query"
    param: str = "page"
    start: int = 1
    max_pages: int = 5


class SourceSettings(BaseModel):
    delay_between_requests: int = 2
    timeout: int = 30
    encoding: str = "utf-8"
    user_agent: str = "EventScraper/1.0"


class SourceConfig(BaseModel):
    id: str
    name: str
    base_url: str
    list_url: str
    region: str = ""
    parser_type: str = "html"
    feed_url: Optional[str] = None
    disabled: bool = False
    pagination: SourcePagination = Field(default_factory=SourcePagination)
    list_selectors: Dict = Field(default_factory=dict)
    detail_selectors: Dict = Field(default_factory=dict)
    json_fields: Dict = Field(default_factory=dict)
    settings: SourceSettings = Field(default_factory=SourceSettings)

    VALID_PARSERS: ClassVar[Set[str]] = {
        "html", "rss", "ical", "manual",
        "kulturnik", "kulturnik-rss",
        "mgml", "kinodvor", "kinosiska",
        "mojaobcina", "cankarjevdom", "visitskofjaloka",
    }

    @field_validator("parser_type")
    @classmethod
    def valid_parser(cls, v):
        if v not in cls.VALID_PARSERS:
            raise ValueError(f"Neznan parser_type: '{v}'. Dovoljeni: {sorted(cls.VALID_PARSERS)}")
        return v


class SourceFile(BaseModel):
    source: SourceConfig


# =====================================================================
# MEDIJI
# =====================================================================

class MediaConfig(BaseModel):
    id: str
    name: str
    url: Optional[str] = ""
    primary_regions: List[str] = Field(default_factory=list)
    secondary_regions: List[str] = Field(default_factory=list)


class MediaFile(BaseModel):
    media: List[MediaConfig]
    all_sources: Optional[Dict] = None


# =====================================================================
# VALIDACIJA
# =====================================================================

class ValidationResult:
    def __init__(self):
        self.errors = []
        self.warnings = []
        self.sources_loaded = 0
        self.media_loaded = 0

    def add_error(self, src, msg):
        self.errors.append(f"[{src}] {msg}")

    def add_warning(self, src, msg):
        self.warnings.append(f"[{src}] {msg}")

    @property
    def ok(self):
        return not self.errors


def validate_all(config_dir: str) -> ValidationResult:
    """Validira vse YAML datoteke v config_dir."""
    result = ValidationResult()

    # 1. Mediji
    media_path = os.path.join(config_dir, "media.yaml")
    if not os.path.exists(media_path):
        result.add_error("media.yaml", "datoteka ne obstaja")
        return result
    try:
        with open(media_path, "r", encoding="utf-8") as f:
            media_data = yaml.safe_load(f) or {}
        MediaFile(**media_data)
        result.media_loaded = len(media_data.get("media", []))
    except (ValidationError, yaml.YAMLError) as e:
        result.add_error("media.yaml", str(e)[:300])

    # 2. Viri
    sources_dir = os.path.join(config_dir, "sources")
    if not os.path.isdir(sources_dir):
        result.add_error("sources/", "mapa ne obstaja")
        return result

    seen_ids = set()
    for fn in sorted(os.listdir(sources_dir)):
        if not fn.endswith(".yaml"):
            continue
        path = os.path.join(sources_dir, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            sf = SourceFile(**data)
            sid = sf.source.id
            if sid in seen_ids:
                result.add_error(fn, f"podvojen source.id: '{sid}'")
            seen_ids.add(sid)
            if sid != fn[:-5]:  # ime datoteke == id
                result.add_warning(fn, f"ime datoteke se ne ujema z id ('{sid}')")
            result.sources_loaded += 1
        except (ValidationError, yaml.YAMLError) as e:
            result.add_error(fn, str(e)[:300])

    return result


def assert_valid_or_die(config_dir: str):
    """Pokliči ob startupu. Če ni veljavno, exit z razumljivim sporočilom."""
    res = validate_all(config_dir)
    if not res.ok:
        print("=" * 60)
        print("KONFIGURACIJA NI VELJAVNA — sistem ne more startati:")
        print("=" * 60)
        for err in res.errors:
            print(f"  ERROR: {err}")
        for warn in res.warnings:
            print(f"  WARN:  {warn}")
        raise SystemExit(1)
    if res.warnings:
        print("Konfiguracija OK z opozorili:")
        for warn in res.warnings:
            print(f"  WARN: {warn}")
    return res
