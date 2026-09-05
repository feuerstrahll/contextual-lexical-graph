from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import Pos, SemanticConcept, WordSense


engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
client = TestClient(app)


def override_get_db() -> Generator[Session, None, None]:
    with TestingSessionLocal() as session:
        yield session


def setup_module() -> None:
    Base.metadata.create_all(engine)
    with TestingSessionLocal() as session:
        concept = SemanticConcept(synset_id="test.n.01", definition="test")
        session.add(concept)
        session.flush()
        session.add_all(
            [
                WordSense(
                    lemma="improve",
                    pos=Pos.verb,
                    gloss="make better",
                    frequency_rank=1,
                    concept_id=concept.id,
                ),
                WordSense(
                    lemma="improvement",
                    pos=Pos.noun,
                    gloss="the act of improving",
                    frequency_rank=2,
                    concept_id=concept.id,
                ),
            ]
        )
        session.commit()
    app.dependency_overrides[get_db] = override_get_db


def teardown_module() -> None:
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_search_returns_senses_ranked_by_frequency() -> None:
    response = client.get("/api/search", params={"q": "improve"})

    assert response.status_code == 200
    assert response.json() == [
        {"senseId": 1, "lemma": "improve", "pos": "verb", "gloss": "make better"},
        {
            "senseId": 2,
            "lemma": "improvement",
            "pos": "noun",
            "gloss": "the act of improving",
        },
    ]


def test_search_handles_a_typo() -> None:
    response = client.get("/api/search", params={"q": "imporve"})

    assert response.status_code == 200
    assert response.json()[0]["lemma"] == "improve"
