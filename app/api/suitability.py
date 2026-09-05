import re
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ContextRule, EdgeType, LexicalEdge, Pos, WordSense

router = APIRouter(prefix="/api", tags=["suitability"])


class SuitabilityDimensions(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    semantic: float | None
    grammar: float | None
    collocation: float | None
    register_value: float | None = Field(alias="register", serialization_alias="register")
    naturalness: float | None


class MatchedRule(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    rule_id: int = Field(validation_alias="id", serialization_alias="ruleId")
    frame: str
    subject_type: str | None = Field(serialization_alias="subjectType")
    object_type: str | None = Field(serialization_alias="objectType")
    register_value: str | None = Field(alias="register", serialization_alias="register")


class SuitabilityResponse(BaseModel):
    score: float | None
    dimensions: SuitabilityDimensions
    matched_rule: MatchedRule | None = Field(serialization_alias="matchedRule")
    confidence: float
    reason: str | None


@dataclass(frozen=True)
class RuleMatch:
    rule: ContextRule
    object_matches: bool
    subject_matches: bool


@router.get("/edges/{edge_id}/suitability", response_model=SuitabilityResponse)
def get_suitability(
    edge_id: int,
    context_sentence: str = Query(min_length=1, max_length=1000),
    db: Session = Depends(get_db),
) -> SuitabilityResponse:
    edge = db.get(LexicalEdge, edge_id)
    if edge is None or edge.curator_status.value != "published":
        raise HTTPException(status_code=404, detail="Published edge not found")

    source = db.get(WordSense, edge.source_sense_id)
    target = db.get(WordSense, edge.target_sense_id)
    if source is None or target is None:
        raise HTTPException(status_code=404, detail="Edge senses not found")

    rules = db.scalars(select(ContextRule).where(ContextRule.edge_id == edge_id)).all()
    match = _match_rule(rules, context_sentence)
    if match is None:
        return SuitabilityResponse(
            score=None,
            dimensions=SuitabilityDimensions(
                semantic=None,
                grammar=None,
                collocation=None,
                register_value=None,
                naturalness=None,
            ),
            matched_rule=None,
            confidence=0.0,
            reason="No context rule matches this sentence",
        )

    dimensions = _score_dimensions(edge, source, target, match, context_sentence)
    score, confidence = _aggregate(dimensions, source.pos)
    return SuitabilityResponse(
        score=score,
        dimensions=dimensions,
        matched_rule=MatchedRule.model_validate(match.rule),
        confidence=confidence,
        reason=None,
    )


def _match_rule(rules: list[ContextRule], sentence: str) -> RuleMatch | None:
    normalized = _tokens(sentence)
    candidates: list[tuple[int, RuleMatch]] = []
    for rule in rules:
        object_matches = _constraint_matches(rule.object_type, normalized)
        subject_matches = _constraint_matches(rule.subject_type, normalized)
        frame_tokens = _frame_tokens(rule.frame)
        frame_matches = not frame_tokens or all(
            _token_matches(token, normalized) for token in frame_tokens
        )
        if frame_matches and (object_matches or subject_matches or not rule.object_type and not rule.subject_type):
            specificity = int(object_matches) + int(subject_matches) + len(frame_tokens)
            candidates.append((specificity, RuleMatch(rule, object_matches, subject_matches)))
    return max(candidates, key=lambda candidate: candidate[0])[1] if candidates else None


def _score_dimensions(
    edge: LexicalEdge,
    source: WordSense,
    target: WordSense,
    match: RuleMatch,
    sentence: str,
) -> SuitabilityDimensions:
    semantic = edge.base_substitutability
    grammar = 1.0 if source.pos == target.pos else 0.0
    collocation = float(match.object_matches) if match.rule.object_type else None
    register_value = None
    naturalness = _naturalness(match.rule, sentence)
    return SuitabilityDimensions(
        semantic=semantic,
        grammar=grammar,
        collocation=collocation,
        register_value=register_value,
        naturalness=naturalness,
    )


def _aggregate(dimensions: SuitabilityDimensions, pos: Pos) -> tuple[float | None, float]:
    weights = {
        Pos.verb: {"semantic": 0.30, "grammar": 0.30, "collocation": 0.20, "register": 0.10, "naturalness": 0.10},
        Pos.noun: {"semantic": 0.35, "grammar": 0.20, "collocation": 0.30, "register": 0.10, "naturalness": 0.05},
        Pos.adjective: {"semantic": 0.35, "grammar": 0.25, "collocation": 0.20, "register": 0.10, "naturalness": 0.10},
        Pos.adverb: {"semantic": 0.35, "grammar": 0.25, "collocation": 0.20, "register": 0.10, "naturalness": 0.10},
    }[pos]
    values = dimensions.model_dump(by_alias=True)
    measured = [(weights[name], value) for name, value in values.items() if value is not None]
    if not measured:
        return None, 0.0
    total_weight = sum(weight for weight, _ in measured)
    score = sum(weight * value for weight, value in measured) / total_weight
    confidence = total_weight / sum(weights.values())
    return round(score, 4), round(confidence, 4)


def _constraint_matches(constraint: str | None, sentence_tokens: set[str]) -> bool:
    if not constraint:
        return False
    return any(_token_matches(token, sentence_tokens) for token in _tokens(constraint))


def _token_matches(token: str, sentence_tokens: set[str]) -> bool:
    normalized_tokens = {word.rstrip("s") for word in sentence_tokens}
    return token in sentence_tokens or token.rstrip("s") in normalized_tokens or any(
        word.startswith(token) for word in sentence_tokens if len(token) >= 4
    )


def _frame_tokens(frame: str) -> set[str]:
    ignored = {"verb", "noun", "adjective", "adverb", "subject", "object", "the", "a", "an"}
    return {token for token in _tokens(frame) if token not in ignored and not token.startswith("{")}


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z]+", value.casefold()))


def _naturalness(rule: ContextRule, sentence: str) -> float | None:
    examples = _tokens(rule.valid_examples or "")
    sentence_tokens = _tokens(sentence)
    if not examples or not sentence_tokens:
        return None
    overlap = len(examples & sentence_tokens) / len(sentence_tokens)
    return round(min(1.0, overlap), 4)
