#!/bin/bash
set -e

APP_ENV="${APP_ENV:-production}"
ENABLE_DEV_SEEDS="${ENABLE_DEV_SEEDS:-false}"

echo "🚀 Iniciando SAA29..."

# Garantir que o diretório de uploads exista no volume
if [ -n "$UPLOAD_DIR" ]; then
    echo "📁 Criando diretório de uploads em $UPLOAD_DIR..."
    mkdir -p "$UPLOAD_DIR"
fi

# 0. Instalação automática de dependências (Garante que novos pacotes no requirements.txt sejam instalados)
echo "📦 Verificando/Instalando dependências (Auto-update)..."
pip install --no-cache-dir -r requirements.txt

# 0. Restaurar backup do R2 (se configurado)
# (Desabilitado temporariamente para testes locais com banco zerado)
# if [ -n "$R2_BUCKET_NAME" ]; then
#     echo "🔄 Restaurando banco de dados do Cloudflare R2..."
#     python scripts/maintenance/r2_manager.py restore
# fi

# 1. Executar migrações do banco
echo "🔄 Rodando migrações (Alembic)..."
python -m alembic upgrade head

# 2. Inicialização básica (Sempre roda, só cria o que não existe)
echo "🔧 Inicializando banco de dados (Bootstrap)..."
python -m scripts.db.init_db

# 3. Popular dados de teste apenas com flag explícita fora de produção
if [ "$APP_ENV" != "production" ] && [ "$ENABLE_DEV_SEEDS" = "true" ]; then
    echo "🌱 Populando dados de teste (Seed)..."
    python -m scripts.db.seed
    python -m scripts.seed_equipamentos
    python -m scripts.seed_30_panes
else
    echo "⏭️ Seed de desenvolvimento desabilitada."
fi

# 4. Iniciar a aplicação
echo "✨ Iniciando servidor Gunicorn..."
exec gunicorn -c gunicorn_conf.py app.bootstrap.main:app
