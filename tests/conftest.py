"""
Skupne fixture za teste.
Uporablja in-memory SQLite bazo za izolacijo.
"""

import os
import sys
import pytest

# Dodaj project root v path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from database.models import Base, Event, MediaOutlet, event_media
from datetime import date, datetime


@pytest.fixture
def db_session():
    """In-memory SQLite DB za teste."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()

    yield session

    session.close()
    Session.remove()
    Base.metadata.drop_all(engine)


@pytest.fixture
def sample_event(db_session):
    """Testni dogodek."""
    event = Event(
        title="Testni koncert",
        description="Opis testnega koncerta v Ljubljani.",
        date_start=date(2026, 5, 15),
        date_end=date(2026, 5, 15),
        time_start="20:00",
        time_end="22:00",
        location="Cankarjev dom",
        address="Prešernova cesta 10, Ljubljana",
        price="15 EUR",
        organizer="CD Ljubljana",
        categories="koncert",
        event_type="koncert",
        target_audience="vsi",
        image_url="https://example.com/img.jpg",
        source_url="https://example.com/event/1",
        detail_url="https://example.com/event/1",
        source_id="test-source",
        source_event_id="test-1",
        region="ljubljana",
        dedup_hash="abc123",
    )
    db_session.add(event)
    db_session.commit()
    return event


@pytest.fixture
def sample_media(db_session):
    """Testna medija."""
    media = MediaOutlet(
        id="testportal",
        name="Test Portal",
        url="https://testportal.si",
        regions='["ljubljana", "slovenija"]',
    )
    db_session.add(media)
    db_session.commit()
    return media


@pytest.fixture
def app_client():
    """Flask test client."""
    from web.app import app
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"

    with app.test_client() as client:
        yield client
