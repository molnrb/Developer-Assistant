from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., description="The username of the user.")
    email: EmailStr = Field(..., description="The email of the user.")
    password: str = Field(..., description="The password of the user.")


class LoginRequest(BaseModel):
    username: str = Field(..., description="The username of the user.")
    password: str = Field(..., description="The password of the user.")


class Token(BaseModel):
    access_token: str = Field(..., description="The access token for the user.")
    token_type: str = Field(
        ..., description="The type of the token (usually 'bearer')."
    )
