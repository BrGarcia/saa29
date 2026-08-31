#!/bin/bash
# ============================================================================
# SAA29 — Configuração de Domínio Próprio + HTTPS/SSL na VPS
# ============================================================================
#
# Descrição: Configura Nginx + Let's Encrypt para o domínio saa29.com.br,
#            registrado no registro.br.
#
# Substitui o antigo `setup_ssl.sh`, que assumia um subdomínio DuckDNS.
# Com um domínio próprio o DuckDNS deixou de ser necessário.
#
# Uso:
#   1. Conferir as variáveis do bloco CONFIGURAÇÃO abaixo
#   2. Transferir para a VPS:  scp -P 22022 setup_dominio_saa29.sh usuario@143.95.216.54:~
#   3. Executar na VPS:        chmod +x setup_dominio_saa29.sh && sudo ./setup_dominio_saa29.sh
#
# PRÉ-REQUISITOS (o script valida os dois primeiros e aborta se falharem):
#   - Registro A de saa29.com.br já apontando para o IP público da VPS
#   - Registro A (ou CNAME) de www.saa29.com.br idem
#   - Portas 80 e 443 liberadas no painel Hostgator
#   - Aplicação SAA29 rodando na porta 8000
#
# Data: 2026-08-21
# ============================================================================

set -euo pipefail

# =========================
# CONFIGURAÇÃO — EDITAR AQUI
# =========================
DOMAIN="saa29.com.br"                 # Domínio principal (registro.br)
INCLUDE_WWW="true"                    # "true" inclui www.${DOMAIN} no certificado
APP_PORT="8000"                       # Porta onde o Gunicorn/Uvicorn está rodando
EMAIL=""                              # Email para avisos de expiração do Let's Encrypt
MAX_UPLOAD_SIZE="50M"                 # Tamanho máximo de upload via Nginx

# Porta do SSH desta VPS. NÃO é 22 — o Hostgator usa 22022.
# Esta variável existe porque o script pode ativar o ufw: liberar a porta errada
# aqui derruba o seu próprio acesso à máquina, sem volta pela rede.
SSH_PORT="22022"
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

# Lista de domínios cobertos pelo certificado
if [ "$INCLUDE_WWW" = "true" ]; then
    SERVER_NAMES="${DOMAIN} www.${DOMAIN}"
else
    SERVER_NAMES="${DOMAIN}"
fi

echo ""
echo "============================================"
echo "  SAA29 — Domínio próprio + HTTPS/SSL"
echo "  Domínios: ${SERVER_NAMES}"
echo "============================================"
echo ""

# Verificar se está rodando como root
if [ "$(id -u)" -ne 0 ]; then
    log_error "Este script deve ser executado como root (sudo)."
    exit 1
fi

# ============================================================================
# Verificação de DNS
# ============================================================================

log_info "Verificando resolução DNS..."

command -v dig >/dev/null 2>&1 || apt-get install -y -qq dnsutils >/dev/null 2>&1

SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "desconhecido")
log_info "IP público desta VPS: ${SERVER_IP}"

for d in $SERVER_NAMES; do
    RESOLVED_IP=$(dig +short A "$d" | tail -1)

    if [ -z "$RESOLVED_IP" ]; then
        log_error "${d} não resolve para nenhum IP."
        log_error "Cadastre o registro A no painel do registro.br e aguarde a propagação."
        log_error "Conferir com: dig +short A ${d}"
        exit 1
    fi

    if [ "$RESOLVED_IP" != "$SERVER_IP" ]; then
        log_warn "${d} resolve para ${RESOLVED_IP}, mas esta VPS é ${SERVER_IP}."
        log_warn "O certbot vai falhar se o DNS não apontar para cá."
        read -p "Continuar mesmo assim? (s/N): " confirm
        if [[ ! "$confirm" =~ ^[sS]$ ]]; then
            log_info "Abortado pelo usuário."
            exit 0
        fi
    else
        log_success "DNS OK — ${d} → ${RESOLVED_IP}"
    fi
done

# ============================================================================
# Verificação da aplicação
# ============================================================================

if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${APP_PORT}" | grep -qE "^[2-4]"; then
    log_success "Aplicação respondendo na porta ${APP_PORT}."
else
    log_warn "Aplicação não parece estar rodando na porta ${APP_PORT}."
    log_warn "O Nginx será configurado, mas responderá 502 até a app subir."
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

if [ -f "$NGINX_SITE_FILE" ]; then
    BACKUP_FILE="${NGINX_SITE_FILE}.bak_$(date +%Y%m%d_%H%M%S)"
    cp "$NGINX_SITE_FILE" "$BACKUP_FILE"
    log_info "Backup da config anterior salvo em ${BACKUP_FILE}"
fi

cat > "$NGINX_SITE_FILE" <<EOF
# ============================================
# SAA29 — Nginx Virtual Host
# Gerado automaticamente em $(date '+%Y-%m-%d %H:%M:%S')
# ============================================

server {
    listen 80;
    server_name ${SERVER_NAMES};

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

ln -sf "$NGINX_SITE_FILE" "$NGINX_ENABLED_LINK"

if [ -f /etc/nginx/sites-enabled/default ]; then
    log_info "Removendo config 'default' do Nginx para evitar conflito..."
    rm -f /etc/nginx/sites-enabled/default
fi

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
    # A porta do SSH é liberada ANTES de qualquer ativação do ufw. Se o ufw
    # subir sem esta regra, a conexão atual cai e não há como reentrar.
    ufw allow "${SSH_PORT}/tcp" > /dev/null 2>&1 || true
    log_success "SSH liberado na porta ${SSH_PORT}."

    ufw allow 80/tcp  > /dev/null 2>&1 || true
    ufw allow 443/tcp > /dev/null 2>&1 || true

    if ! ufw status | grep -q "Status: active"; then
        log_warn "UFW não está ativo."
        log_warn "Confirme que a porta ${SSH_PORT} está na lista acima antes de ativar."
        read -p "Ativar o ufw agora? (s/N): " confirm_ufw
        if [[ "$confirm_ufw" =~ ^[sS]$ ]]; then
            echo "y" | ufw enable > /dev/null 2>&1
            log_success "UFW ativado."
        else
            log_info "UFW deixado inativo. Portas 80/443 dependem do painel Hostgator."
        fi
    fi

    ufw status numbered || true
else
    log_warn "UFW não encontrado. Verifique manualmente se portas 80/443 estão abertas."
fi

# ============================================================================
# Passo 4 — Obter certificado SSL
# ============================================================================

log_info "Passo 4/5 — Obtendo certificado SSL via Let's Encrypt..."

CERTBOT_ARGS="--nginx --non-interactive --agree-tos --redirect"

for d in $SERVER_NAMES; do
    CERTBOT_ARGS="${CERTBOT_ARGS} -d ${d}"
done

if [ -n "$EMAIL" ]; then
    CERTBOT_ARGS="${CERTBOT_ARGS} --email ${EMAIL}"
else
    log_warn "EMAIL vazio — sem aviso de expiração do Let's Encrypt."
    CERTBOT_ARGS="${CERTBOT_ARGS} --register-unsafely-without-email"
fi

if certbot $CERTBOT_ARGS; then
    log_success "Certificado SSL obtido e configurado!"
else
    log_error "Falha ao obter o certificado. Verifique:"
    log_error "  - DNS de ${SERVER_NAMES} aponta para ${SERVER_IP}?"
    log_error "  - Portas 80/443 abertas no painel Hostgator?"
    log_error "  - Limite do Let's Encrypt (5 falhas/hora por domínio) atingido?"
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
echo -e "  ${GREEN}✅ DOMÍNIO E HTTPS CONFIGURADOS!${NC}"
echo "============================================"
echo ""
echo "  🌐 URL segura:  https://${DOMAIN}"
echo "  🔒 Certificado: Let's Encrypt (válido por 90 dias)"
echo "  🔄 Renovação:   Automática"
echo "  📦 Nginx:       Proxy reverso para porta ${APP_PORT}"
echo ""
echo -e "  ${YELLOW}FALTA AJUSTAR A APLICAÇÃO:${NC}"
echo "  No .env da VPS, defina e reinicie os containers:"
echo ""
echo "    ALLOWED_HOSTS=${DOMAIN},www.${DOMAIN}"
echo "    ALLOWED_ORIGINS=https://${DOMAIN},https://www.${DOMAIN}"
echo "    FORCE_SECURE_COOKIES=true"
echo ""
echo "  Sem isso os cookies de sessão continuam sem o atributo Secure."
echo ""
echo "============================================"
