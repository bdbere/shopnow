import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional

from fastapi.security import OAuth2PasswordRequestForm
from seguridad import verificar_token

app = FastAPI(
    title="Departamento de Clientes",
    dependencies=[Depends(verificar_token)],
    description="Servicio encargado de la custodia y registro oficial de los clientes de la empresa. \n\n" \
    "Este servicio actúa como el punto central de integración para la validación de clientes en los procesos de venta y atención al cliente. \n\n" \
    "Ejecutar en puerto **8000** y asegurarse de que los servicios de Pedidos (8002) y Productos (8001) estén activos para su correcto funcionamiento.",
    version="3.0.0", 
    contact={
        "name": "Berenice Hernandez ISC - TecNM Querétaro",
    }
)

class Cliente(BaseModel):
    id_cliente: int = Field(..., example=101)
    nombre: str = Field(..., min_length=3, example="Juan Pérez")
    correo: EmailStr = Field(..., example="juan@ejemplo.com")
    direccion: Optional[str] = Field(None, example="Calle 123")
    telefono: Optional[str] = Field(None, example="555-1234")
    activo: bool = Field(True, example=True)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class ClienteRegistro(BaseModel):
    nombre: str = Field(..., min_length=3, example="Juan Pérez")
    correo: EmailStr = Field(..., example="juan@ejemplo.com")
    direccion: Optional[str] = Field(None, example="Calle 123")
    telefono: Optional[str] = Field(None, example="555-1234")

class ClienteUpdate(BaseModel):
    nombre: Optional[str] = Field(None, min_length=3)
    correo: Optional[EmailStr] = Field(None)
    direccion: Optional[str] = Field(None)
    telefono: Optional[str] = Field(None)
    activo: Optional[bool] = Field(None)



DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)

def obtener_conexion():
    """Establece la conexión con PostgreSQL usando un cursor de diccionario."""
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def ejecutar_consulta(query: str, params: tuple = (), fetch_one=False, fetch_all=False):
    """Función ayudante para ejecutar comandos SQL sin repetir código."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    resultado = None
    try:
        cursor.execute(query, params)
        if fetch_one:
            resultado = cursor.fetchone()
        elif fetch_all:
            resultado = cursor.fetchall()
        conexion.commit()
    except Exception as e:
        conexion.rollback()
        raise HTTPException(status_code=500, detail=f"Error en la base de datos: {e}")
    finally:
        cursor.close()
        conexion.close()
    return resultado

#ENDPOINTS DE SEGURIDAD 
@app.post("/token", tags=["Seguridad"], summary="Generar token de acceso JWT",
    responses={
        200: {"description": "Autenticación exitosa y generación de token"},
        401: {"description": "Credenciales inválidas"}
    })
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    query = "SELECT * FROM clientes WHERE correo = %s AND activo = true;"
    cliente = ejecutar_consulta(query, (form_data.username,), fetch_one=True)
    
    if not cliente or form_data.password != "itq123":
        raise HTTPException(
            status_code=401, 
            detail="Correo o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    token = crear_token_acceso(data={
        "sub": cliente['correo'], 
        "id_cliente": cliente['id_cliente'],
        "nombre": cliente['nombre']
    })
    return {"access_token": token, "token_type": "bearer"}


@app.get("/clientes", response_model=List[Cliente], tags=["Clientes"],
         summary="Obtener lista de clientes",
    status_code=200,
    responses={
        200: {
            "description": "Lista de clientes obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id_cliente": 101,
                            "nombre": "Juan Pérez",
                            "correo": "juan@ejemplo.com",
                            "direccion": "Calle 123",
                            "telefono": "555-1234",
                            "activo": True,
                            "created_at": "2026-05-13T10:00:00",
                            "updated_at": None
                        }
                    ]
                }
            }
        }
    })
def obtener_clientes():
    """Retorna todos los clientes"""
    query = "SELECT * FROM clientes ORDER BY id_cliente ASC;"
    return ejecutar_consulta(query, fetch_all=True)

@app.get("/clientes/{id_cliente}", response_model=Cliente, tags=["Clientes"],
         summary="Obtener un cliente por ID",
    responses={
        200: {"description": "Cliente encontrado"},
        404: {"description": "Cliente no encontrado o inactivo"}
    }
)
    
def obtener_cliente_por_id(id_cliente: int):
    """Retorna un cliente específico si está activo."""
    query = "SELECT * FROM clientes WHERE id_cliente = %s AND activo = true;"
    cliente = ejecutar_consulta(query, (id_cliente,), fetch_one=True)
    
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    return cliente

@app.post("/clientes", status_code=201, tags=["Clientes"],
          summary="Registrar nuevo cliente",
    responses={
        201: {
            "description": "Cliente registrado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "mensaje": "Cliente registrado exitosamente",
                        "id_cliente": 102,
                        "created_at": "2026-05-13T10:05:00"
                    }
                }
            }
        },
        422: {"description": "Datos de entrada inválidos"}
    }
)
def registrar_cliente(nuevo: ClienteRegistro):
    """Registra un nuevo cliente. La BD genera el ID y los timestamps automáticamente."""
    query = "CALL hb_clientes_agregar(%s, %s, %s, %s);"
    params = (nuevo.nombre, nuevo.correo, nuevo.direccion, nuevo.telefono)
    
    resultado = ejecutar_consulta(query, params)
    
    return {
        "mensaje": "Cliente registrado exitosamente"
    }

@app.patch("/clientes/{id_cliente}", tags=["Clientes"],
           summary="Actualizar cliente parcialmente",
    status_code=200,
    responses={
        200: {
            "description": "Cliente actualizado exitosamente",
            "content": {
                "application/json": {
                    "example": {"mensaje": "Cliente actualizado parcialmente exitosamente"}
                }
            }
        },
        404: {"description": "Cliente no encontrado"}
    }
)
def actualizar_cliente_parcial(id_cliente: int, update: ClienteUpdate):
    """Actualiza parcialmente un cliente usando un Procedimiento Almacenado."""
    # Validamos que al menos haya mandado algo
    update_data = update.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="No se enviaron datos para actualizar")
    
    
    query = "CALL hb_clientes_actualizar(%s, %s, %s, %s, %s, %s);"
    
    # Le pasamos el ID y los 4 campos. Si el usuario no mandó alguno, update.campo valdrá None
    params = (
        id_cliente,
        update.nombre,
        update.correo,
        update.direccion,
        update.telefono,
        update.activo
    )
    
    # Ejecutamos sin esperar retorno
    ejecutar_consulta(query, params)
    
    return {"mensaje": "Cliente actualizado parcialmente exitosamente mediante SP"}

@app.delete("/clientes/{id_cliente}", tags=["Clientes"],
    summary="Eliminar cliente (Soft Delete)",
    status_code=200,
    responses={
        200: {
            "description": "Cliente desactivado exitosamente",
            "content": {
                "application/json": {
                    "example": {"mensaje": "Cliente eliminado exitosamente (Soft Delete)"}
                }
            }
        },
        404: {"description": "Cliente no encontrado"}
    }
)
def eliminar_cliente(id_cliente: int):
    """Aplica una baja lógica (Soft Delete) y actualiza la fecha de modificación."""
    query = "CALL hb_clientes_eliminar(%s);"
    eliminado = ejecutar_consulta(query, (id_cliente,))
    
        
    return {"mensaje": "Cliente eliminado exitosamente (Soft Delete)"}