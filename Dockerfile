FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema para psycopg2 e python-magic
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar diretório de uploads
RUN mkdir -p uploads

EXPOSE 8000

# Usar Gunicorn por padrão (recomendado para produção com Uvicorn workers)
CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]
