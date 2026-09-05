from collections import deque

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import literal, or_, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import CuratorStatus, EdgeType, LexicalEdge, WordSense

router = APIRouter(prefix="/api", tags=["graph"])


class GraphNode(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sense_id: int = Field(validation_alias="id", serialization_alias="senseId")
    lemma: str
    pos: str
    gloss: str


class GraphEdge(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    edge_id: int = Field(validation_alias="id", serialization_alias="edgeId")
    source_sense_id: int = Field(
        validation_alias="source_sense_id", serialization_alias="sourceSenseId"
    )
    target_sense_id: int = Field(
        validation_alias="target_sense_id", serialization_alias="targetSenseId"
    )
    edge_type: EdgeType = Field(serialization_alias="edgeType")
    directed: bool
    semantic_similarity: float | None = Field(serialization_alias="semanticSimilarity")
    base_substitutability: float | None = Field(serialization_alias="baseSubstitutability")


class GraphResponse(BaseModel):
    center: GraphNode
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    depth: int


@router.get("/senses/{sense_id}/graph", response_model=GraphResponse)
def get_graph(
    sense_id: int,
    depth: int = Query(default=1, ge=0, le=2),
    relation_types: list[EdgeType] | None = Query(default=None),
    mode: str = Query(default="linguistic", pattern="^(linguistic|personal)$"),
    db: Session = Depends(get_db),
) -> GraphResponse:
    del mode
    center = db.get(WordSense, sense_id)
    if center is None:
        raise HTTPException(status_code=404, detail="Sense not found")

    allowed_types = set(relation_types) if relation_types else None
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        sense_ids, edge_rows = _postgresql_neighborhood(db, sense_id, depth, allowed_types)
    else:
        sense_ids, edge_rows = _portable_neighborhood(db, sense_id, depth, allowed_types)

    senses = db.scalars(select(WordSense).where(WordSense.id.in_(sense_ids))).all()
    nodes_by_id = {sense.id: GraphNode.model_validate(sense) for sense in senses}
    edges = [GraphEdge.model_validate(edge) for edge in edge_rows]
    nodes = [nodes_by_id[node_id] for node_id in sense_ids if node_id in nodes_by_id]
    return GraphResponse(center=nodes_by_id[sense_id], nodes=nodes, edges=edges, depth=depth)


def _edge_filter(statement, allowed_types: set[EdgeType] | None):
    statement = statement.where(LexicalEdge.curator_status == CuratorStatus.published)
    if allowed_types:
        statement = statement.where(LexicalEdge.edge_type.in_(allowed_types))
    return statement


def _portable_neighborhood(
    db: Session, center_id: int, depth: int, allowed_types: set[EdgeType] | None
) -> tuple[list[int], list[LexicalEdge]]:
    visited = {center_id}
    frontier = deque([center_id])
    edge_by_id: dict[int, LexicalEdge] = {}

    for _ in range(depth):
        next_frontier: list[int] = []
        while frontier:
            current_id = frontier.popleft()
            statement = _edge_filter(
                select(LexicalEdge).where(
                    or_(
                        LexicalEdge.source_sense_id == current_id,
                        (LexicalEdge.target_sense_id == current_id)
                        & (LexicalEdge.directed.is_(False)),
                    )
                ),
                allowed_types,
            )
            for edge in db.scalars(statement).all():
                edge_by_id[edge.id] = edge
                neighbor_id = (
                    edge.target_sense_id
                    if edge.source_sense_id == current_id
                    else edge.source_sense_id
                )
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    next_frontier.append(neighbor_id)
        frontier.extend(next_frontier)

    return list(visited), list(edge_by_id.values())


def _postgresql_neighborhood(
    db: Session, center_id: int, depth: int, allowed_types: set[EdgeType] | None
) -> tuple[list[int], list[LexicalEdge]]:
    base = select(
        literal(center_id).label("sense_id"),
        literal(0).label("level"),
    )
    traversal = base.cte("neighborhood", recursive=True)
    current = select(LexicalEdge.source_sense_id, traversal.c.level + 1).join(
        traversal, LexicalEdge.target_sense_id == traversal.c.sense_id
    )
    reverse = select(LexicalEdge.target_sense_id, traversal.c.level + 1).join(
        traversal,
        (LexicalEdge.source_sense_id == traversal.c.sense_id)
        & (LexicalEdge.directed.is_(False)),
    )
    current = _edge_filter(current, allowed_types).where(traversal.c.level < depth)
    reverse = _edge_filter(reverse, allowed_types).where(traversal.c.level < depth)
    traversal = traversal.union_all(current, reverse)
    id_rows = db.execute(select(traversal.c.sense_id.distinct())).all()
    sense_ids = [row[0] for row in id_rows]
    edge_statement = _edge_filter(
        select(LexicalEdge).where(
            LexicalEdge.source_sense_id.in_(sense_ids),
            LexicalEdge.target_sense_id.in_(sense_ids),
        ),
        allowed_types,
    )
    return sense_ids, list(db.scalars(edge_statement).all())
