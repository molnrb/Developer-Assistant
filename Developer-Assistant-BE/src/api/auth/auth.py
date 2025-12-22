from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.hash import bcrypt
from pymongo.collection import Collection

from src.api.auth.auth_dto import LoginRequest, RegisterRequest, Token
from src.api.auth.auth_database import get_user_collection
from src.config import ALGORITHM, SECRET_KEY

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")


router = APIRouter()


@router.post("/register")
async def register_user(
    data: RegisterRequest, users: Collection = Depends(get_user_collection)
):
    if users.find_one({"email": data.email}):
        raise HTTPException(status_code=400, detail="Email already registered.")

    hashed_pw = bcrypt.hash(data.password)

    users.insert_one(
        {
            "username": data.username,
            "email": data.email,
            "password": hashed_pw,
            "created_at": datetime.utcnow(),
        }
    )

    access_token = create_access_token(data={"sub": data.username})
    return {"access_token": access_token, "token_type": "bearer"}


async def authenticate_user(collection: Collection, username: str, password: str):
    user = collection.find_one({"username": username})
    if not user:
        return None
    if not bcrypt.verify(password, user["password"]):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(hours=24))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


@router.post("/login", response_model=Token)
async def login(data: LoginRequest, users: Collection = Depends(get_user_collection)):
    user = await authenticate_user(users, data.username, data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user["username"]})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me")
async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: no subject",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return {"username": username}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.get("/debug/token_info")
async def debug_token_info(token: str = Depends(oauth2_scheme)):
    """
    Debug JWT token: returns decoded payload if valid, else 401.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return {
            "valid": True,
            "token_payload": payload,
            "secret_key_used": SECRET_KEY,
        }
    except JWTError as e:
        return {
            "valid": False,
            "error": str(e),
            "secret_key_used": SECRET_KEY,
        }
