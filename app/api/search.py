from difflib import SequenceMatcher

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.api.schemas import SenseSearchResult
from app.db import get_db
from app.models import WordSense

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=list[SenseSearchResult])
def search_senses(
    q: str = Query(min_length=1, max_length=120),
    db: Session = Depends(get_db),
) -> list[SenseSearchResult]:
    query = q.strip()
    if not query:
        return []

    if db.bind is not None and db.bind.dialect.name == "postgresql":
        return _search_postgresql(db, query)
    return _search_without_trigram(db, query)


def _search_postgresql(db: Session, query: str) -> list[SenseSearchResult]:
    similarity = func.similarity(WordSense.lemma, query)
    full_text_match = func.to_tsvector("simple", WordSense.lemma).op("@@")(
        func.plainto_tsquery("simple", query)
    )
    statement = (
        select(WordSense)
        .where(or_(full_text_match, WordSense.lemma.ilike(f"%{query}%"), similarity >= 0.3))
        .order_by(WordSense.frequency_rank.is_(None), WordSense.frequency_rank, similarity.desc())
    )
    return [SenseSearchResult.model_validate(sense) for sense in db.scalars(statement).all()]


def _search_without_trigram(db: Session, query: str) -> list[SenseSearchResult]:
    normalized_query = query.casefold()
    senses = db.scalars(select(WordSense)).all()
    matches = [
        sense
        for sense in senses
        if normalized_query in sense.lemma.casefold()
        or SequenceMatcher(None, normalized_query, sense.lemma.casefold()).ratio() >= 0.3
    ]
    matches.sort(key=lambda sense: (sense.frequency_rank is None, sense.frequency_rank or 0))
    return [SenseSearchResult.model_validate(sense) for sense in matches]
