#!/bin/bash
set -e

echo "🚀 Iniciando SAA29..."

# 1. Executar migrações do banco
echo "🔄 Rodando migrações (Alembic)..."
python -m alembic upgrade head

# 2. Popular dados iniciais (seed)
# O script de seed agora é idempotente e usa variáveis de ambiente
echo "🌱 Populando banco de dados..."
python -m scripts.seed

# 3. Iniciar a aplicação
echo "✨ Iniciando servidor Gunicorn..."
exec gunicorn -c gunicorn_conf.py app.main:app
