from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt
from dotenv import load_dotenv
import os

load_dotenv()  

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

api_key_scheme = APIKeyHeader(name="Authorization")

token_blacklist=set()

def get_current_user(token: str = Depends(api_key_scheme)):
    if not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    jwt_token = token.split("Bearer ")[1]
    if jwt_token in token_blacklist:
        raise HTTPException(status_code=401,detail="Token has been revoked")
    try:
        payload = jwt.decode(jwt_token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username, "token": jwt_token}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
