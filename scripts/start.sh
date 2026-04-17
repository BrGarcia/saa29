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
    python scripts/r2_manager.py restore
fi

# 1. Executar migrações do banco
echo "🔄 Rodando migrações (Alembic)..."
python -m alembic upgrade head

# 2. Inicialização básica (Sempre roda, só cria o que não existe)
echo "🔧 Inicializando banco de dados (Bootstrap)..."
python -m scripts.init_db

# 3. Popular dados de teste (Apenas se em desenvolvimento)
if [ "$APP_ENV" == "development" ]; then
    echo "🌱 Populando dados de teste (Seed)..."
    python -m scripts.seed
fi

# 4. Iniciar a aplicação
echo "✨ Iniciando servidor Gunicorn..."
exec gunicorn -c gunicorn_conf.py app.main:app
