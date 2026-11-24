from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Color = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
IdemKey = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=100)]
# Teto de segurança: R$ 1 bilhão em centavos.
MAX_CENTS = 100_000_000_000


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)
