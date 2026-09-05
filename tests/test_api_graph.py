from collections.abc import Generator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import CuratorStatus, EdgeType, LexicalEdge, Pos, SemanticConcept, WordSense


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
        concept = SemanticConcept(synset_id="graph.v.01", definition="make better")
        session.add(concept)
        session.flush()
        senses = [
            WordSense(lemma="improve", pos=Pos.verb, gloss="make better", concept_id=concept.id),
            WordSense(lemma="enhance", pos=Pos.verb, gloss="make better", concept_id=concept.id),
            WordSense(lemma="boost", pos=Pos.verb, gloss="increase", concept_id=concept.id),
        ]
        session.add_all(senses)
        session.flush()
        session.add_all(
            [
                LexicalEdge(
                    source_sense_id=senses[0].id,
                    target_sense_id=senses[1].id,
                    edge_type=EdgeType.synonym,
                    directed=False,
                    semantic_similarity=0.95,
                    base_substitutability=0.9,
                    curator_status=CuratorStatus.published,
                ),
                LexicalEdge(
                    source_sense_id=senses[1].id,
                    target_sense_id=senses[2].id,
                    edge_type=EdgeType.near_synonym,
                    directed=False,
                    semantic_similarity=0.8,
                    base_substitutability=0.7,
                    curator_status=CuratorStatus.published,
                ),
                LexicalEdge(
                    source_sense_id=senses[0].id,
                    target_sense_id=senses[2].id,
                    edge_type=EdgeType.antonym,
                    directed=False,
                    curator_status=CuratorStatus.candidate,
                ),
            ]
        )
        session.commit()
    app.dependency_overrides[get_db] = override_get_db


def teardown_module() -> None:
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)


def test_graph_depth_one_returns_only_direct_neighbors() -> None:
    response = client.get("/api/senses/1/graph", params={"depth": 1})

    assert response.status_code == 200
    body = response.json()
    assert {node["senseId"] for node in body["nodes"]} == {1, 2}
    assert len(body["edges"]) == 1


def test_graph_depth_two_and_relation_filter() -> None:
    response = client.get(
        "/api/senses/1/graph",
        params=[("depth", "2"), ("relation_types", "NEAR_SYNONYM")],
    )

    assert response.status_code == 200
    body = response.json()
    assert {node["senseId"] for node in body["nodes"]} == {1}
    assert body["edges"] == []

    response = client.get("/api/senses/1/graph", params={"depth": 2})
    assert {node["senseId"] for node in response.json()["nodes"]} == {1, 2, 3}
    assert len(response.json()["edges"]) == 2


def test_graph_returns_404_for_unknown_sense() -> None:
    response = client.get("/api/senses/999/graph")

    assert response.status_code == 404
