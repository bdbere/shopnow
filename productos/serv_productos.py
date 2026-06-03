import os
import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import FastAPI, HTTPException, APIRouter, Depends
from pydantic import BaseModel, Field
from typing import List, Optional

from seguridad import verificar_token

app = FastAPI(
    title="Departamento de Productos",
    dependencies=[Depends(verificar_token)],
    description="Servicio encargado de la custodia y registro oficial del catálogo de productos de la empresa.\n\n" \
    "Demuestra gobernabilidad de APIs mediante versionamiento (V1 y V2).",
    version="3.0.0",
    contact={
        "name": "Berenice Hernández, ISC - TecNM Querétaro",
    }
)

# CONFIGURACIÓN DE BASE DE DATOS
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://shopnow_663n_user:mJKZ4Bs3pW5XqeK5c5FLlukVy1TUGEIl@dpg-d7ohmhpj2pic73abp6l0-a.oregon-postgres.render.com/shopnow_663n"
)

def ejecutar_consulta(query: str, params: tuple = (), fetch_one=False, fetch_all=False):
    """Función ayudante centralizada para ejecutar comandos SQL."""
    conexion = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
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

# MODELOS DE VERSIONADO 1
class ProductoV1(BaseModel):
    id_producto: int = Field(..., example=1)
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer")
    precio: float = Field(..., gt=0, example=15000.0)

class ProductoRegistroV1(BaseModel):
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer")
    precio: float = Field(..., gt=0, example=15000.0)

class ProductoUpdateV1(BaseModel):
    descripcion: Optional[str] = Field(None, min_length=3)
    precio: Optional[float] = Field(None, gt=0)

# MDELOS DE VERSIONADO 2
class ProductoV2(BaseModel):
    id_producto: int = Field(..., example=1)
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer")
    costo_unitario: float = Field(..., gt=0, example=15000.0)

class ProductoRegistroV2(BaseModel):
    descripcion: str = Field(..., min_length=3, example="Laptop Gamer")
    costo_unitario: float = Field(..., gt=0, example=15000.0)

class ProductoUpdateV2(BaseModel):
    descripcion: Optional[str] = Field(None, min_length=3)
    costo_unitario: Optional[float] = Field(None, gt=0)


# ROUTER V1
router_v1 = APIRouter(prefix="/v1/productos", tags=["Productos V1"])

@router_v1.get("", response_model=List[ProductoV1], summary="Obtener todos los productos (V1)")
def obtener_productos_v1():
    return ejecutar_consulta("SELECT * FROM productos ORDER BY id_producto ASC;", fetch_all=True)

@router_v1.get("/{id_producto}", response_model=ProductoV1, summary="Obtener producto por ID (V1)")
def obtener_producto_v1(id_producto: int):
    producto = ejecutar_consulta("SELECT * FROM productos WHERE id_producto = %s;", (id_producto,), fetch_one=True)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return producto

@router_v1.post("", status_code=201, summary="Registrar producto (V1)")
def registrar_producto_v1(nuevo: ProductoRegistroV1):
    query = "CALL hb_productos_agregar(%s, %s);"
    ejecutar_consulta(query, (nuevo.descripcion, nuevo.precio))
    return {"mensaje": "Producto guardado exitosamente mediante SP (V1)", "status": "success"}

@router_v1.patch("/{id_producto}", summary="Actualizar producto parcialmente (V1)")
def actualizar_producto_v1(id_producto: int, update: ProductoUpdateV1):
    existe = ejecutar_consulta("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,), fetch_one=True)
    if not existe:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
        
    query = "CALL hb_productos_actualizar(%s, %s, %s);"
    ejecutar_consulta(query, (id_producto, update.descripcion, update.precio))
    return {"mensaje": "Producto actualizado parcialmente mediante SP (V1)", "status": "success"}

@router_v1.delete("/{id_producto}", summary="Eliminar producto (V1)")
def eliminar_producto_v1(id_producto: int):
    existe = ejecutar_consulta("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,), fetch_one=True)
    if not existe:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
        
    query = "CALL hb_productos_eliminar(%s);"
    ejecutar_consulta(query, (id_producto,))
    return {"mensaje": "Producto eliminado mediante SP (V1)", "status": "success"}


# ROUTER V2
router_v2 = APIRouter(prefix="/v2/productos", tags=["Productos V2"])

@router_v2.get("", response_model=List[ProductoV2], summary="Obtener todos los productos (V2)")
def obtener_productos_v2():
    productos = ejecutar_consulta("SELECT * FROM productos ORDER BY id_producto ASC;", fetch_all=True)
    # Transformamos "precio" a "costo_unitario" para los clientes de la V2
    for p in productos:
        p['costo_unitario'] = p.pop('precio')
    return productos

@router_v2.get("/{id_producto}", response_model=ProductoV2, summary="Obtener producto por ID (V2)")
def obtener_producto_v2(id_producto: int):
    producto = ejecutar_consulta("SELECT * FROM productos WHERE id_producto = %s;", (id_producto,), fetch_one=True)
    if not producto:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # Transformación del campo
    producto['costo_unitario'] = producto.pop('precio')
    return producto

@router_v2.post("", status_code=201, summary="Registrar producto (V2)")
def registrar_producto_v2(nuevo: ProductoRegistroV2):
    
    query = "CALL hb_productos_agregar(%s, %s);"
    ejecutar_consulta(query, (nuevo.descripcion, nuevo.costo_unitario))
    
    query_buscar = "SELECT id_producto FROM productos WHERE descripcion = %s ORDER BY id_producto DESC LIMIT 1;"
    resultado = ejecutar_consulta(query_buscar, (nuevo.descripcion,), fetch_one=True)
    
    return {
        "mensaje": "Producto guardado exitosamente mediante SP (V2)", 
        "status": "success",
        "id_producto": resultado["id_producto"] if resultado else None
    }

@router_v2.patch("/{id_producto}", summary="Actualizar producto parcialmente (V2)")
def actualizar_producto_v2(id_producto: int, update: ProductoUpdateV2):
    existe = ejecutar_consulta("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,), fetch_one=True)
    if not existe:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
        
    query = "CALL hb_productos_actualizar(%s, %s, %s);"
    ejecutar_consulta(query, (id_producto, update.descripcion, update.costo_unitario))
    return {"mensaje": "Producto actualizado parcialmente mediante SP (V2)", "status": "success"}

@router_v2.delete("/{id_producto}", summary="Eliminar producto (V2)")
def eliminar_producto_v2(id_producto: int):
    existe = ejecutar_consulta("SELECT id_producto FROM productos WHERE id_producto = %s;", (id_producto,), fetch_one=True)
    if not existe:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
        
    query = "CALL hb_productos_eliminar(%s);"
    ejecutar_consulta(query, (id_producto,))
    return {"mensaje": "Producto eliminado mediante SP (V2)", "status": "success"}


# REGISTRO DE RUTAS
app.include_router(router_v1)
app.include_router(router_v2)