"""
Podatkovni modeli za dogodke.

PHASE 1 REFACTOR (april 2026):
- Persistent storage: dogodki se ne brišejo več ob scrape, ampak posodabljajo
  ali označujejo kot neaktivni (is_active=False)
- DATABASE_URL podpira tako SQLite (razvoj) kot PostgreSQL (produkcija)
- EventEdit history za audit trail (kdo je kaj spremenil)
- Multi-user attribution (created_by, updated_by)
- Optimistic locking (version stolpec)

Workflow statusi v event_media (NESPREMENJENO):
  new       -> sveže scrapaný, še ni pregledan
  approved  -> urednik potrdil za objavo
  queued    -> v čakalni vrsti za Drupal push
  pushed    -> poslano v Drupal (drupal_nid dodeljen)
  published -> objavljeno na portalu (potrjeno)
  skipped   -> urednik preskočil / ni relevantno
  archived  -> pretekli dogodek, arhiviran
"""

import os
from contextlib import contextmanager
from datetime import datetime, date

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, Date, DateTime,
    Boolean, Float, Table, ForeignKey, UniqueConstraint, Index, JSON,
    event as sa_event,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, scoped_session

# =====================================================================
# DATABASE URL — env-driven, podpira SQLite + PostgreSQL
# =====================================================================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "events.db")

# Pred. vrstni red:
# 1. EVENT_SCRAPER_DATABASE_URL (eksplicitno)
# 2. DATABASE_URL (standardno PostgreSQL)
# 3. fallback: SQLite v data/events.db
DATABASE_URL = (
    os.environ.get("EVENT_SCRAPER_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or f"sqlite:///{DEFAULT_DB_PATH}"
)

# Heroku/Render style: postgres:// → postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

IS_SQLITE = DATABASE_URL.startswith("sqlite")
IS_POSTGRES = DATABASE_URL.startswith("postgresql")

# SQLite specifični nastavitve
if IS_SQLITE:
    os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
    engine_kwargs = {
        "connect_args": {"check_same_thread": False},
        "pool_pre_ping": True,
    }
elif IS_POSTGRES:
    engine_kwargs = {
        "pool_pre_ping": True,
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "10")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "20")),
        "pool_recycle": 3600,
    }
else:
    engine_kwargs = {"pool_pre_ping": True}

engine = create_engine(DATABASE_URL, echo=False, **engine_kwargs)
_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
Session = scoped_session(_session_factory)
Base = declarative_base()

# Pri SQLite vključimo foreign keys
if IS_SQLITE:
    @sa_event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# =====================================================================
# CONTEXT MANAGER za seje
# =====================================================================

@contextmanager
def get_db():
    """Context manager za varno upravljanje DB sej.

    Uporaba:
        with get_db() as db:
            events = db.query(Event).all()
    """
    db = Session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# =====================================================================
# UPORABNIKI (multi-user podpora)
# =====================================================================

class User(Base):
    """Uporabnik dashboarda."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(200), unique=True, nullable=False, index=True)
    name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    role = Column(String(20), default="admin", nullable=False)
    # "admin" = vidi vse medije, "editor" = samo svoje
    allowed_media = Column(Text, nullable=True)
    # JSON seznam media_id-jev (samo za role="editor"); NULL = vsi
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    last_scrape_seen_at = Column(DateTime, nullable=True)
    # Kdaj je uporabnik nazadnje zaprl/potrdil scrape result banner.
    # Banner se prikaže če obstaja scrape z finished_at > last_scrape_seen_at.


# =====================================================================
# VMESNA TABELA: dogodek <-> medij (M:N z metapodatki)
# =====================================================================

event_media = Table(
    "event_media",
    Base.metadata,
    Column("event_id", Integer, ForeignKey("events.id", ondelete="CASCADE"), primary_key=True),
    Column("media_id", String(50), ForeignKey("media_outlets.id", ondelete="CASCADE"), primary_key=True),

    # Workflow status
    Column("status", String(20), default="new", nullable=False),

    # Uredniške odločitve
    Column("priority", Integer, default=0, nullable=False),
    Column("featured", Boolean, default=False, nullable=False),
    Column("editor_notes", Text, nullable=True),

    # Drupal integracija (placeholderji za prihodnost)
    Column("drupal_nid", Integer, nullable=True),
    Column("drupal_status", String(20), nullable=True),

    # Multi-user attribution
    Column("approved_by_user_id", Integer, ForeignKey("users.id"), nullable=True),
    Column("skipped_by_user_id", Integer, ForeignKey("users.id"), nullable=True),

    # Časovni žigi
    Column("assigned_at", DateTime, default=datetime.utcnow),
    Column("approved_at", DateTime, nullable=True),
    Column("pushed_at", DateTime, nullable=True),
    Column("published_at", DateTime, nullable=True),
    Column("processed_at", DateTime, nullable=True),

    Index("idx_em_status", "status"),
    Index("idx_em_media_status", "media_id", "status"),
)


class MediaOutlet(Base):
    """Medij - portal za objavo dogodkov."""
    __tablename__ = "media_outlets"

    id = Column(String(50), primary_key=True)
    name = Column(String(200), nullable=False)
    url = Column(String(500), nullable=True)
    regions = Column(Text, nullable=True)
    drupal_api_url = Column(String(500), nullable=True)
    drupal_api_key = Column(String(200), nullable=True)

    events = relationship("Event", secondary=event_media, back_populates="media_outlets")


# =====================================================================
# DOGODEK (PERSISTENT MODEL)
# =====================================================================

class Event(Base):
    """
    Dogodek - centralni model.

    Persistent storage:
    - is_active: dogodek je viden v dashboardu (False = scraper ga ni več našel)
    - first_seen_at, last_seen_at: kdaj je bil prvič in zadnjič zasedan v scrapu
    - version: optimistic locking (povečamo ob vsakem update)
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # === VSEBINSKI PODATKI ===
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    date_start = Column(Date, nullable=True)
    date_end = Column(Date, nullable=True)
    time_start = Column(String(20), nullable=True)
    time_end = Column(String(20), nullable=True)
    location = Column(String(500), nullable=True)
    address = Column(String(500), nullable=True)
    price = Column(String(200), nullable=True)
    organizer = Column(String(300), nullable=True)
    district = Column(String(200), nullable=True)

    # === KATEGORIZACIJA ===
    categories = Column(String(500), nullable=True)
    event_type = Column(String(100), nullable=True)
    target_audience = Column(String(100), nullable=True)

    # === SLIKE / OPISI ===
    image_url = Column(String(1000), nullable=True)
    image_source = Column(String(20), nullable=True)
    description_source = Column(String(20), nullable=True)
    source_url = Column(String(1000), nullable=True)
    detail_url = Column(String(1000), nullable=True)
    ticket_url = Column(String(1000), nullable=True)

    # === METAPODATKI VIRA ===
    source_id = Column(String(50), nullable=False, index=True)
    source_event_id = Column(String(200), nullable=True)
    region = Column(String(100), nullable=True, index=True)

    # === DEDUPLIKACIJA ===
    dedup_hash = Column(String(64), nullable=True, index=True)

    # === KAKOVOST ===
    quality_score = Column(Float, nullable=True)
    completeness = Column(Float, nullable=True)

    # === PERSISTENT STORAGE STOLPCI (PHASE 1) ===
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    # False = scraper dogodka ni več našel pri zadnjem zagonu (a obdržimo zgodovino)
    first_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # === MULTI-USER ATTRIBUTION ===
    last_edited_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    last_edited_at = Column(DateTime, nullable=True)

    # === OPTIMISTIC LOCKING ===
    version = Column(Integer, default=1, nullable=False)

    # === ČASOVNI ŽIGI ===
    scraped_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # === RELACIJE ===
    media_outlets = relationship("MediaOutlet", secondary=event_media, back_populates="events")
    edits = relationship("EventEdit", back_populates="event", cascade="all, delete-orphan",
                         order_by="EventEdit.created_at.desc()")

    __table_args__ = (
        Index("idx_event_dedup", "dedup_hash"),
        Index("idx_event_date", "date_start"),
        Index("idx_event_active_date", "is_active", "date_start"),
        Index("idx_event_source_active", "source_id", "is_active"),
        UniqueConstraint("source_id", "source_event_id", name="uq_source_event"),
    )

    def __repr__(self):
        return f"<Event id={self.id} '{self.title[:30] if self.title else ''}' {self.date_start}>"

    def calculate_completeness(self):
        fields = [
            self.title, self.description, self.date_start,
            self.time_start, self.location, self.image_url,
            self.organizer, self.categories, self.price,
        ]
        filled = sum(1 for f in fields if f)
        return round(filled / len(fields), 2)

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "date_start": self.date_start.isoformat() if self.date_start else None,
            "date_end": self.date_end.isoformat() if self.date_end else None,
            "time_start": self.time_start,
            "time_end": self.time_end,
            "location": self.location,
            "address": self.address,
            "price": self.price,
            "organizer": self.organizer,
            "categories": self.categories,
            "event_type": self.event_type,
            "target_audience": self.target_audience,
            "district": self.district,
            "image_url": self.image_url,
            "image_source": self.image_source,
            "description_source": self.description_source,
            "source_url": self.source_url,
            "detail_url": self.detail_url,
            "ticket_url": self.ticket_url,
            "source_id": self.source_id,
            "region": self.region,
            "is_active": self.is_active,
            "version": self.version,
            "first_seen_at": self.first_seen_at.isoformat() if self.first_seen_at else None,
            "last_seen_at": self.last_seen_at.isoformat() if self.last_seen_at else None,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
        }


# =====================================================================
# AUDIT TRAIL — zgodovina sprememb dogodka
# =====================================================================

class EventEdit(Base):
    """
    Beleži vsako spremembo polja na Event-u (ročno urejanje, AI generiranje, scraper update).
    Omogoča audit trail in roll-back v prihodnosti.
    """
    __tablename__ = "event_edits"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"),
                      nullable=False, index=True)

    field_name = Column(String(50), nullable=False)
    # title, description, location, organizer, event_type, image_url, ...
    old_value = Column(Text, nullable=True)
    new_value = Column(Text, nullable=True)

    source = Column(String(30), nullable=False, default="manual")
    # "scraper" | "manual" | "ai-generated" | "import" | "auto-enrichment"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    # NULL če je bila sprememba avtomatska (scraper, enrichment)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    event = relationship("Event", back_populates="edits")

    __table_args__ = (
        Index("idx_edit_event_time", "event_id", "created_at"),
        Index("idx_edit_user", "user_id"),
    )


# =====================================================================
# DEDUP DECISION LOG — zakaj smo dva dogodka označili kot duplikat
# =====================================================================

class DedupDecision(Base):
    """
    Beleži vsako odločitev deduplikacije — za diagnostiko false-positive/negative.
    """
    __tablename__ = "dedup_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    incoming_title = Column(String(500), nullable=False)
    incoming_source_id = Column(String(50), nullable=True)
    incoming_date = Column(Date, nullable=True)
    incoming_time = Column(String(10), nullable=True)
    incoming_location = Column(String(500), nullable=True)

    matched_event_id = Column(Integer, ForeignKey("events.id"), nullable=True)
    matched_title = Column(String(500), nullable=True)

    decision = Column(String(20), nullable=False)
    # "duplicate" | "new" | "stale-update"
    reason = Column(String(200), nullable=False)
    # human-readable: "exact_hash", "fuzzy_60_same_time", "exact_normalized_title", ...
    score = Column(Float, nullable=True)
    threshold = Column(Float, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


# =====================================================================
# SCRAPE LOG — nespremenjeno
# =====================================================================

class ScrapeLog(Base):
    """Dnevnik scrapinga - en zapis na vir-zagon."""
    __tablename__ = "scrape_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(50), nullable=False, index=True)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    finished_at = Column(DateTime, nullable=True)
    events_found = Column(Integer, default=0)
    events_new = Column(Integer, default=0)
    events_updated = Column(Integer, default=0)      # Phase 1: posodobljeni dogodki
    events_duplicate = Column(Integer, default=0)
    events_marked_stale = Column(Integer, default=0)  # Phase 1: dogodki ki jih ni več
    status = Column(String(20), default="running")
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)


class DrupalPushLog(Base):
    """Dnevnik pushev v Drupal - placeholderji za prihodnost."""
    __tablename__ = "drupal_push_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False)
    media_id = Column(String(50), ForeignKey("media_outlets.id"), nullable=False)
    drupal_nid = Column(Integer, nullable=True)
    action = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False)
    response_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    pushed_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("idx_push_event", "event_id"),
        Index("idx_push_media", "media_id"),
    )


class SourceHealth(Base):
    """Zdravje vira - razširjeno z metrikami za retry/backoff."""
    __tablename__ = "source_health"

    source_id = Column(String(50), primary_key=True)
    source_name = Column(String(200), nullable=True)
    parser_type = Column(String(50), nullable=True)

    last_check = Column(DateTime, nullable=True)
    last_success = Column(DateTime, nullable=True)
    last_error = Column(DateTime, nullable=True)
    last_error_msg = Column(Text, nullable=True)
    last_events_found = Column(Integer, default=0)

    success_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)
    total_events_7d = Column(Integer, default=0)
    avg_events = Column(Float, default=0)
    avg_duration_ms = Column(Float, default=0)  # Phase 1: povprečni čas

    status = Column(String(20), default="unknown")
    consecutive_errors = Column(Integer, default=0, nullable=False)
    consecutive_successes = Column(Integer, default=0, nullable=False)  # Phase 1
    last_retry_count = Column(Integer, default=0)  # Phase 1: koliko retry-jev je bilo potrebnih

    list_url = Column(String(1000), nullable=True)
    feed_url = Column(String(1000), nullable=True)
    notes = Column(Text, nullable=True)


class UnprocessedUrl(Base):
    """URL-ji ki jih scraper ne zna obdelati."""
    __tablename__ = "unprocessed_urls"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_id = Column(String(50), nullable=False)
    url = Column(String(1000), nullable=False)
    reason = Column(String(200), nullable=True)
    page_title = Column(String(500), nullable=True)
    content_type = Column(String(100), nullable=True)
    response_code = Column(Integer, nullable=True)
    status = Column(String(20), default="pending")
    resolution = Column(Text, nullable=True)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_unprocessed_source", "source_id"),
        Index("idx_unprocessed_status", "status"),
    )


# =====================================================================
# UTILITIES
# =====================================================================

def init_db():
    """Ustvari vse tabele (uporablja se za prve teste in setup brez Alembic)."""
    Base.metadata.create_all(engine)
    return DATABASE_URL


def database_info():
    """Vrne kratek opis trenutne DB povezave (za health endpoint)."""
    import re
    safe_url = re.sub(r"://[^@]+@", "://***:***@", DATABASE_URL)
    return {
        "url": safe_url,
        "dialect": "postgresql" if IS_POSTGRES else ("sqlite" if IS_SQLITE else "other"),
    }


if __name__ == "__main__":
    print(f"DATABASE_URL: {database_info()['url']}")
    init_db()
    print("Vse tabele ustvarjene.")
