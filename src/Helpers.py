from passlib.context import CryptContext
import jwt
import datetime
import json
from datetime import datetime, timedelta
from Database import *
from flask import request
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET", "4c284965492e20ff581e9195e000f116f74516fc2a15d8d19707eb44267da762")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM" , "HS256")
JWT_EXP_SECONDS = int(os.getenv("JWT_EXP_SECONDS", 7200))

def ensure_indexes():
    try:
        orgs_coll.create_index([("organization_name", ASCENDING)], unique=True)
        admins_coll.create_index([("email", ASCENDING)], unique=True)
        admins_coll.create_index([("org_id", ASCENDING)])
    except Exception as e:
        print("Index creation issue:", e)


def hash_password(password: str) -> str:
    return pwd_ctx.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def create_jwt(admin_id: str, org_id: str, email: str, role: str = "owner"):
    now = datetime.utcnow()
    payload = {
        "sub": admin_id,
        "org_id": org_id,
        "email": email,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=JWT_EXP_SECONDS)
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token if isinstance(token, str) else token.decode("utf-8")

def decode_jwt_from_header():
    auth = request.headers.get("Authorization", None)
    if not auth:
        return None, ("Missing Authorization header", 401)
    parts = auth.split()
    if parts[0].lower() != "bearer" or len(parts) != 2:
        return None, ("Invalid Authorization header format", 401)
    token = parts[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return None, ("Token expired", 401)
    except jwt.InvalidTokenError:
        return None, ("Invalid token", 401)
    return payload, None
