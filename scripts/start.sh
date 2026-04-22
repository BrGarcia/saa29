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
    python scripts/maintenance/r2_manager.py restore
fi

# 1. Executar migrações do banco
echo "🔄 Rodando migrações (Alembic)..."
python -m alembic upgrade head

# 2. Inicialização básica (Sempre roda, só cria o que não existe)
echo "🔧 Inicializando banco de dados (Bootstrap)..."
python scripts/db/init_db.py

# 3. Popular dados de teste (Apenas se em desenvolvimento)
if [ "$APP_ENV" == "development" ]; then
    echo "🌱 Populando dados de teste (Seed)..."
    python scripts/db/seed.py
    python scripts/seed_equipamentos.py
    python scripts/seed_30_panes.py
fi

# 4. Iniciar a aplicação
echo "✨ Iniciando servidor Gunicorn..."
exec gunicorn -c gunicorn_conf.py app.bootstrap.main:app
