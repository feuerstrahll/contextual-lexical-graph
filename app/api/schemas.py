from pydantic import BaseModel, ConfigDict, Field

from app.models import Pos


class SenseSearchResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    sense_id: int = Field(validation_alias="id", serialization_alias="senseId")
    lemma: str
    pos: Pos
    gloss: str
