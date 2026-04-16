FROM python:3.12-slim

WORKDIR /app

# Dependências do sistema para python-magic
RUN apt-get update && apt-get install -y \
    gcc \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

# Criar diretório de uploads
RUN mkdir -p uploads && \
    sed -i 's/\r$//' scripts/start.sh && \
    chmod +x scripts/start.sh

EXPOSE 8000

# Usar o script de inicialização para rodar migrações e seed antes do app
CMD ["/bin/bash", "scripts/start.sh"]

