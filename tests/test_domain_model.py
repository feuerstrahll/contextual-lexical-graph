from app.db import Base
import app.models  # noqa: F401


def test_domain_model_contains_architecture_entities() -> None:
    expected_tables = {
        "word_senses",
        "semantic_concepts",
        "semantic_clusters",
        "lexical_edges",
        "context_rules",
        "transformation_rules",
        "exercises",
        "attempts",
        "edge_mastery",
        "context_mastery",
        "content_versions",
    }

    assert expected_tables == set(Base.metadata.tables)
