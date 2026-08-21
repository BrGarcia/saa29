#!/bin/bash
# ============================================================================
# SAA29 — Script de Configuração HTTPS/SSL na VPS
# ============================================================================
#
# Descrição: Automatiza a instalação e configuração de HTTPS com Let's Encrypt
#            para o SAA29 rodando atrás de Nginx em Ubuntu/Debian.
#
# Uso:
#   1. Editar a variável DOMAIN abaixo com seu subdomínio DuckDNS
#   2. Transferir para a VPS:  scp setup_ssl.sh usuario@ip-da-vps:~
#   3. Executar na VPS:        chmod +x setup_ssl.sh && sudo ./setup_ssl.sh
#
# IMPORTANTE: Antes de executar, certifique-se de que:
#   - O subdomínio DuckDNS já está criado e apontando para o IP da VPS
#   - As portas 80 e 443 estão liberadas no painel do Hostgator
#   - A aplicação SAA29 está rodando na porta 8000
#
# Data: 2026-08-21
# ============================================================================

set -euo pipefail

# =========================
# CONFIGURAÇÃO — EDITAR AQUI
# =========================
DOMAIN="saa29.duckdns.org"           # ← Substituir pelo seu subdomínio DuckDNS
APP_PORT="8000"                       # Porta onde o Gunicorn/Uvicorn está rodando
EMAIL=""                              # Email para notificações do Let's Encrypt (opcional)
MAX_UPLOAD_SIZE="50M"                 # Tamanho máximo de upload via Nginx
# =========================

NGINX_SITE_FILE="/etc/nginx/sites-available/saa29"
NGINX_ENABLED_LINK="/etc/nginx/sites-enabled/saa29"

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()    { echo -e "${BLUE}[INFO]${NC}  $1"; }
log_success() { echo -e "${GREEN}[OK]${NC}    $1"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error()   { echo -e "${RED}[ERRO]${NC}  $1"; }

# ============================================================================
# Verificações iniciais
# ============================================================================

echo ""
echo "============================================"
echo "  SAA29 — Setup HTTPS/SSL"
echo "  Domínio: ${DOMAIN}"
echo "============================================"
echo ""

# Verificar se está rodando como root
if [ "$(id -u)" -ne 0 ]; then
    log_error "Este script deve ser executado como root (sudo)."
    exit 1
fi

# Verificar se o domínio foi alterado do padrão
if [ "$DOMAIN" = "saa29.duckdns.org" ]; then
    log_warn "Usando domínio padrão '${DOMAIN}'."
    log_warn "Certifique-se de que este é o subdomínio correto no DuckDNS."
    read -p "Continuar? (s/N): " confirm
    if [[ ! "$confirm" =~ ^[sS]$ ]]; then
        log_info "Abortado pelo usuário."
        exit 0
    fi
fi

# Verificar resolução DNS
log_info "Verificando resolução DNS de ${DOMAIN}..."
RESOLVED_IP=$(dig +short "$DOMAIN" 2>/dev/null || echo "")
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "desconhecido")

if [ -z "$RESOLVED_IP" ]; then
    log_error "Não foi possível resolver ${DOMAIN}."
    log_error "Verifique se o subdomínio está configurado no DuckDNS."
    exit 1
fi

if [ "$RESOLVED_IP" != "$SERVER_IP" ]; then
    log_warn "DNS resolve para ${RESOLVED_IP}, mas o IP deste servidor é ${SERVER_IP}."
    log_warn "Verifique a configuração do DuckDNS."
    read -p "Continuar mesmo assim? (s/N): " confirm
    if [[ ! "$confirm" =~ ^[sS]$ ]]; then
        exit 0
    fi
else
    log_success "DNS OK — ${DOMAIN} → ${RESOLVED_IP}"
fi

# Verificar se a aplicação está rodando
if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${APP_PORT}" | grep -qE "^[2-4]"; then
    log_success "Aplicação respondendo na porta ${APP_PORT}."
else
    log_warn "Aplicação não parece estar rodando na porta ${APP_PORT}."
    log_warn "O Nginx será configurado, mas pode retornar 502 até a app iniciar."
fi

# ============================================================================
# Passo 1 — Instalar dependências
# ============================================================================

log_info "Passo 1/5 — Instalando Certbot e dependências..."

apt-get update -qq
apt-get install -y -qq certbot python3-certbot-nginx dnsutils curl > /dev/null 2>&1

log_success "Certbot instalado."

# ============================================================================
# Passo 2 — Configurar Nginx
# ============================================================================

log_info "Passo 2/5 — Configurando Nginx..."

# Backup da configuração existente (se houver)
if [ -f "$NGINX_SITE_FILE" ]; then
    BACKUP_FILE="${NGINX_SITE_FILE}.bak_$(date +%Y%m%d_%H%M%S)"
    cp "$NGINX_SITE_FILE" "$BACKUP_FILE"
    log_info "Backup da config anterior salvo em ${BACKUP_FILE}"
fi

# Criar configuração do site
cat > "$NGINX_SITE_FILE" <<EOF
# ============================================
# SAA29 — Nginx Virtual Host
# Gerado automaticamente em $(date '+%Y-%m-%d %H:%M:%S')
# ============================================

server {
    listen 80;
    server_name ${DOMAIN};

    # Tamanho máximo de upload
    client_max_body_size ${MAX_UPLOAD_SIZE};

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
EOF

# Ativar o site
ln -sf "$NGINX_SITE_FILE" "$NGINX_ENABLED_LINK"

# Remover default se existir e conflitar
if [ -f /etc/nginx/sites-enabled/default ]; then
    log_info "Removendo config 'default' do Nginx para evitar conflito..."
    rm -f /etc/nginx/sites-enabled/default
fi

# Testar e recarregar
if nginx -t 2>/dev/null; then
    systemctl reload nginx
    log_success "Nginx configurado e recarregado."
else
    log_error "Erro na configuração do Nginx. Verifique com: nginx -t"
    exit 1
fi

# ============================================================================
# Passo 3 — Configurar Firewall
# ============================================================================

log_info "Passo 3/5 — Configurando firewall (ufw)..."

if command -v ufw &> /dev/null; then
    ufw allow 80/tcp  > /dev/null 2>&1 || true
    ufw allow 443/tcp > /dev/null 2>&1 || true
    
    # Garantir que SSH continua permitido
    ufw allow 22/tcp  > /dev/null 2>&1 || true
    
    # Ativar ufw se não estiver ativo (com cuidado)
    if ! ufw status | grep -q "Status: active"; then
        log_warn "UFW não está ativo. Ativando..."
        echo "y" | ufw enable > /dev/null 2>&1
    fi
    
    log_success "Firewall configurado (80, 443, 22 liberadas)."
else
    log_warn "UFW não encontrado. Verifique manualmente se portas 80/443 estão abertas."
fi

# ============================================================================
# Passo 4 — Obter certificado SSL
# ============================================================================

log_info "Passo 4/5 — Obtendo certificado SSL via Let's Encrypt..."

CERTBOT_ARGS="--nginx -d ${DOMAIN} --non-interactive --agree-tos"

if [ -n "$EMAIL" ]; then
    CERTBOT_ARGS="${CERTBOT_ARGS} --email ${EMAIL}"
else
    CERTBOT_ARGS="${CERTBOT_ARGS} --register-unsafely-without-email"
fi

if certbot $CERTBOT_ARGS; then
    log_success "Certificado SSL obtido e configurado!"
else
    log_error "Falha ao obter o certificado. Verifique:"
    log_error "  - DNS está apontando para este servidor?"
    log_error "  - Portas 80/443 estão abertas no painel Hostgator?"
    exit 1
fi

# ============================================================================
# Passo 5 — Verificar renovação automática
# ============================================================================

log_info "Passo 5/5 — Verificando renovação automática..."

if systemctl is-active --quiet certbot.timer; then
    log_success "Timer de renovação automática está ativo."
else
    log_warn "Timer do certbot não encontrado. Configurando cron..."
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --post-hook 'systemctl reload nginx'") | crontab -
    log_success "Cron de renovação configurado (diariamente às 03:00)."
fi

# Teste de renovação
log_info "Testando renovação (dry-run)..."
if certbot renew --dry-run > /dev/null 2>&1; then
    log_success "Teste de renovação OK."
else
    log_warn "Teste de renovação falhou, mas o certificado atual está válido."
fi

# ============================================================================
# Resumo Final
# ============================================================================

echo ""
echo "============================================"
echo -e "  ${GREEN}✅ HTTPS/SSL CONFIGURADO COM SUCESSO!${NC}"
echo "============================================"
echo ""
echo "  🌐 URL segura:  https://${DOMAIN}"
echo "  🔒 Certificado: Let's Encrypt (válido por 90 dias)"
echo "  🔄 Renovação:   Automática"
echo "  📦 Nginx:       Proxy reverso para porta ${APP_PORT}"
echo ""
echo "  Teste agora acessando: https://${DOMAIN}"
echo ""
echo "============================================"
