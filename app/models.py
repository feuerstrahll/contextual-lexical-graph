from datetime import datetime
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Pos(StrEnum):
    noun = "noun"
    verb = "verb"
    adjective = "adjective"
    adverb = "adverb"


class EdgeType(StrEnum):
    synonym = "SYNONYM"
    near_synonym = "NEAR_SYNONYM"
    paraphrase = "PARAPHRASE"
    register_shift = "REGISTER_SHIFT"
    grammatical_transformation = "GRAMMATICAL_TRANSFORMATION"
    collocation_alternative = "COLLOCATION_ALTERNATIVE"
    hypernym = "HYPERNYM"
    hyponym = "HYPONYM"
    antonym = "ANTONYM"


class CuratorStatus(StrEnum):
    candidate = "candidate"
    reviewed = "reviewed"
    published = "published"
    rejected = "rejected"


class SemanticConcept(Base):
    __tablename__ = "semantic_concepts"

    id: Mapped[int] = mapped_column(primary_key=True)
    synset_id: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    definition: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(40), default="WordNet")


class WordSense(Base):
    __tablename__ = "word_senses"

    id: Mapped[int] = mapped_column(primary_key=True)
    lemma: Mapped[str] = mapped_column(String(120), index=True)
    pos: Mapped[Pos] = mapped_column(Enum(Pos, name="pos"))
    gloss: Mapped[str] = mapped_column(Text)
    cefr: Mapped[str | None] = mapped_column(String(2))
    frequency_rank: Mapped[int | None] = mapped_column(Integer)
    example_sentences: Mapped[str | None] = mapped_column(Text)
    concept_id: Mapped[int] = mapped_column(ForeignKey("semantic_concepts.id"), index=True)


class LexicalEdge(Base):
    __tablename__ = "lexical_edges"
    __table_args__ = (UniqueConstraint("source_sense_id", "target_sense_id", "edge_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_sense_id: Mapped[int] = mapped_column(ForeignKey("word_senses.id"), index=True)
    target_sense_id: Mapped[int] = mapped_column(ForeignKey("word_senses.id"), index=True)
    edge_type: Mapped[EdgeType] = mapped_column(Enum(EdgeType, name="edge_type"))
    directed: Mapped[bool] = mapped_column(Boolean, default=True)
    semantic_similarity: Mapped[float | None] = mapped_column(Float)
    base_substitutability: Mapped[float | None] = mapped_column(Float)
    curator_status: Mapped[CuratorStatus] = mapped_column(
        Enum(CuratorStatus, name="curator_status"), default=CuratorStatus.candidate
    )
    graph_version_id: Mapped[int | None] = mapped_column(ForeignKey("content_versions.id"))


class TransformationRule(Base):
    __tablename__ = "transformation_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    edge_id: Mapped[int] = mapped_column(ForeignKey("lexical_edges.id"), index=True)
    source_frame: Mapped[str] = mapped_column(Text)
    target_frame: Mapped[str] = mapped_column(Text)
    operations: Mapped[str] = mapped_column(Text)
    before_example: Mapped[str] = mapped_column(Text)
    after_example: Mapped[str] = mapped_column(Text)


class ContextRule(Base):
    __tablename__ = "context_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    edge_id: Mapped[int] = mapped_column(ForeignKey("lexical_edges.id"), index=True)
    frame: Mapped[str] = mapped_column(Text)
    subject_type: Mapped[str | None] = mapped_column(String(120))
    object_type: Mapped[str | None] = mapped_column(String(120))
    register: Mapped[str | None] = mapped_column(String(40))
    explanation: Mapped[str] = mapped_column(Text)
    valid_examples: Mapped[str] = mapped_column(Text)
    invalid_examples: Mapped[str] = mapped_column(Text)


class SemanticCluster(Base):
    __tablename__ = "semantic_clusters"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class Exercise(Base):
    __tablename__ = "exercises"

    id: Mapped[int] = mapped_column(primary_key=True)
    exercise_type: Mapped[str] = mapped_column(String(60))
    target_sense_id: Mapped[int] = mapped_column(ForeignKey("word_senses.id"), index=True)
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[str] = mapped_column(Text)
    correct_sense_ids: Mapped[str] = mapped_column(Text)
    partial_sense_ids: Mapped[str | None] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    curator_status: Mapped[CuratorStatus] = mapped_column(
        Enum(CuratorStatus, name="exercise_curator_status"), default=CuratorStatus.candidate
    )
    graph_version_id: Mapped[int | None] = mapped_column(ForeignKey("content_versions.id"))


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    exercise_id: Mapped[int] = mapped_column(ForeignKey("exercises.id"), index=True)
    selected_sense_id: Mapped[int] = mapped_column(ForeignKey("word_senses.id"))
    score: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20))
    reason_code: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EdgeMastery(Base):
    __tablename__ = "edge_mastery"
    __table_args__ = (UniqueConstraint("user_id", "edge_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    edge_id: Mapped[int] = mapped_column(ForeignKey("lexical_edges.id"))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_tested: Mapped[datetime | None] = mapped_column(DateTime)
    next_review: Mapped[datetime | None] = mapped_column(DateTime)


class ContextMastery(Base):
    __tablename__ = "context_mastery"
    __table_args__ = (UniqueConstraint("user_id", "edge_id", "context_rule_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String(120), index=True)
    edge_id: Mapped[int] = mapped_column(ForeignKey("lexical_edges.id"))
    context_rule_id: Mapped[int] = mapped_column(ForeignKey("context_rules.id"))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    last_tested: Mapped[datetime | None] = mapped_column(DateTime)
    next_review: Mapped[datetime | None] = mapped_column(DateTime)


class ContentVersion(Base):
    __tablename__ = "content_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(30), unique=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
