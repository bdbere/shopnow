import jwt
from datetime import datetime, timedelta
from fastapi import HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


SECRET_KEY = "super_llave_secreta_shopnow_2026"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Esto le dice a FastAPI dónde debe ir el usuario a buscar su token
# (Habilitará el botón verde "Authorize" en Swagger UI)
security_scheme = HTTPBearer()

def crear_token_acceso(data: dict):
    """Genera un JWT firmado criptográficamente."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    # Se genera y firma el token usando la llave secreta
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verificar_token(credentials: HTTPAuthorizationCredentials = Security(security_scheme)):
    """Desencripta y valida el token entrante."""
    # HTTPBearer guarda el string del token dentro de .credentials
    token = credentials.credentials 
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token ha expirado. Por favor, inicia sesión de nuevo.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido o manipulado criptográficamente.")