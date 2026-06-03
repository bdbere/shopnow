import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime, timedelta

# Configuración del Token
SECRET_KEY = "clave_secreta_super_segura_del_tecnm"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="http://localhost:8002/token")

# CREDENCIALES ÚNICAS DEL ADMINISTRADOR (ESTO ES LO QUE NO ENCUENTRA)
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "password123"

def crear_token_acceso(data: dict):
    """Genera el token JWT encriptado con una vigencia de tiempo."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def verificar_token(token: str = Depends(oauth2_scheme)):
    """Middleware que intercepta TODAS las peticiones para validar el token."""
    excepcion_credenciales = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Acceso denegado. Token inválido, expirado o ausente.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Desencriptamos el token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        
        # Validamos que el token pertenezca al admin
        if username != ADMIN_USERNAME:
            raise excepcion_credenciales
            
        return payload
    except jwt.PyJWTError:
        # Si el token es inventado o caducó, se lanza este error
        raise excepcion_credenciales