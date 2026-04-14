#!/bin/bash
set -e

echo "🚀 Iniciando SAA29..."

# Garantir que o diretório de uploads exista no volume
if [ -n "$UPLOAD_DIR" ]; then
    echo "📁 Criando diretório de uploads em $UPLOAD_DIR..."
    mkdir -p "$UPLOAD_DIR"
fi

# 0. Restaurar backup do R2 (se configurado)
if [ -n "$R2_BUCKET_NAME" ]; then
    echo "🔄 Restaurando banco de dados do Cloudflare R2..."
    python scripts/backup_r2.py restore
fi

# 1. Executar migrações do banco
echo "🔄 Rodando migrações (Alembic)..."
python -m alembic upgrade head

# 2. Popular dados iniciais (seed)
echo "🌱 Populando banco de dados..."
python -m scripts.seed

# 3. Iniciar a aplicação
echo "✨ Iniciando servidor Gunicorn..."
exec gunicorn -c gunicorn_conf.py app.main:app
