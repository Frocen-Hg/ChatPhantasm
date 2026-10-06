from pydantic import BaseModel


class CharacterCreate(BaseModel):
    card: dict
    ext: dict | None = None


class CharacterUpdate(BaseModel):
    card: dict | None = None
    ext: dict | None = None