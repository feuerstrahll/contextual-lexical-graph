from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import ContextRule, CuratorStatus, EdgeType, LexicalEdge, Pos, SemanticConcept, WordSense


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
        concept = SemanticConcept(synset_id="suitability.v.01", definition="make better")
        session.add(concept)
        session.flush()
        source = WordSense(lemma="improve", pos=Pos.verb, gloss="make better", concept_id=concept.id)
        target = WordSense(lemma="enhance", pos=Pos.verb, gloss="make better", concept_id=concept.id)
        session.add_all([source, target])
        session.flush()
        edge = LexicalEdge(
            source_sense_id=source.id,
            target_sense_id=target.id,
            edge_type=EdgeType.near_synonym,
            directed=False,
            semantic_similarity=0.94,
            base_substitutability=0.89,
            curator_status=CuratorStatus.published,
        )
        session.add(edge)
        session.flush()
        session.add(
            ContextRule(
                edge_id=edge.id,
                frame="improve {object}",
                object_type="skills",
                register="academic",
                explanation="Both words can work with skills in this context.",
                valid_examples="The course improved academic skills.",
                invalid_examples="The course enhanced to the room.",
            )
        )
        session.commit()
    app.dependency_overrides[get_db] = override_get_db


def teardown_module() -> None:
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_suitability_matches_rule_and_returns_measured_dimensions() -> None:
    response = client.get(
        "/api/edges/1/suitability",
        params={"context_sentence": "The course improved academic skills."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["matchedRule"]["ruleId"] == 1
    assert body["score"] == 0.9633
    assert body["dimensions"] == {
        "semantic": 0.89,
        "grammar": 1.0,
        "collocation": 1.0,
        "register": None,
        "naturalness": 1.0,
    }
    assert body["confidence"] == 0.9
    assert body["reason"] is None


def test_unmatched_context_is_explicitly_unmeasurable() -> None:
    response = client.get(
        "/api/edges/1/suitability",
        params={"context_sentence": "The paint covered the wall."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["score"] is None
    assert body["matchedRule"] is None
    assert body["reason"] == "No context rule matches this sentence"
    assert body["confidence"] == 0.0


def test_unpublished_edge_is_not_available() -> None:
    with TestingSessionLocal() as session:
        session.query(LexicalEdge).update({LexicalEdge.curator_status: CuratorStatus.candidate})
        session.commit()

    response = client.get(
        "/api/edges/1/suitability",
        params={"context_sentence": "The course improved academic skills."},
    )

    assert response.status_code == 404
