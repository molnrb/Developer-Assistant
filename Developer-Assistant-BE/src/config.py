import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "0e6e9c1f30b74b7ca7f513e34ac9cf99c4fc527a63923d49bc154117812e8d8a",
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
