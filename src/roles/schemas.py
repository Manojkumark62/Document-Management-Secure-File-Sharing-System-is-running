from pydantic import BaseModel, ConfigDict, Field


class RoleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_-]*$")
    description: str | None = Field(default=None, max_length=255)


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=50, pattern=r"^[a-z][a-z0-9_-]*$")
    description: str | None = Field(default=None, max_length=255)


class RoleResponse(BaseModel):
    id: int
    name: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class RoleAssignment(BaseModel):
    role_names: list[str] = Field(min_length=1)


class UserRolesResponse(BaseModel):
    user_id: int
    roles: list[str]