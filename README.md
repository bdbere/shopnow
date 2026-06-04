#  ShopNow - E-Commerce Microservices Architecture

Bienvenido a **ShopNow**, un sistema de gestión de ventas y catálogo estructurado bajo una Arquitectura Orientada a Servicios (SOA). Este proyecto demuestra la implementación de microservicios independientes, comunicación síncrona/asíncrona y seguridad mediante tokens JWT.

## Tecnologías Utilizadas
* **Backend:** FastAPI (Python)
* **Frontend:** Streamlit
* **Base de Datos:** PostgreSQL (Implementación de *Stored Procedures* y *Triggers*)
* **Mensajería Asíncrona:** RabbitMQ
* **Seguridad:** JWT (JSON Web Tokens) e inyección de dependencias
* **Despliegue:** Docker y Render

## Arquitectura del Sistema
El ecosistema está compuesto por 4 microservicios principales que interactúan entre sí:

1. **Servicio de Clientes (Puerto 8000)**
   * Gestión del padrón de clientes.
   * Implementación de *Soft Delete* (Baja lógica).
2. **Servicio de Productos (Puerto 8001)**
   * Catálogo de artículos con versionamiento de API (V1/V2).
   * Filtros de estado activo/inactivo.
3. **Servicio de Pedidos / Orquestador (Puerto 8002)**
   * Punto de entrada principal y validación de tokens JWT.
   * Comunicación **síncrona** (HTTP/REST) con Clientes y Productos para validar reglas de negocio.
   * Comunicación **asíncrona** con Inventario para procesamiento de existencias.
4. **Servicio de Inventario (Puerto 8003)**
   * Gestión de stock en tiempo real.
   * Consumidor de RabbitMQ para deducción y compensación de inventario (Ej. Cancelaciones).

## Características Destacadas
* **Control Preventivo de Stock:** La interfaz gráfica evalúa el inventario en tiempo real, bloqueando la compra si no hay existencias suficientes.
* **Transacciones Seguras:** Uso de Procedimientos Almacenados en PostgreSQL para garantizar la atomicidad de los datos.
* **UI Dinámica y Reactiva:** Interfaces construidas con Streamlit, utilizando cuadros de diálogo (`st.dialog`) y cruce de datos en caliente para evitar la exposición de IDs crudos.
* **Prevención de Doble Ejecución:** Sincronización perfecta entre los Triggers de la base de datos y la cola de mensajes de RabbitMQ.

## Autora
* **Berenice Hernández** - *Ingeniería en Sistemas Computacionales, TecNM Querétaro.*
