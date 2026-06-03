# 1. Usar una imagen oficial de Python ligera
FROM python:3.9-slim

# 2. Evitar que Python guarde archivos caché y que la consola se retrase
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 3. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 4. Copiar el archivo de dependencias e instalarlas
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar todo el código de tu microservicio al contenedor
COPY . .

# 6. Exponer el puerto por defecto (Render lo sobreescribe, pero es buena práctica)
EXPOSE 8000

# 7. El comando para arrancar la aplicación (cambia "serv_clientes" por el nombre real de tu archivo py en cada carpeta)
CMD ["uvicorn", "serv_clientes:app", "--host", "0.0.0.0", "--port", "8000"]