# Configuração HTTPS/SSL na VPS

> **Status:** 📋 Pendente de execução  
> **Prioridade:** Alta  
> **Data:** 2026-08-21  

---

## 1. Contexto do Problema

Ao acessar o SAA29 pela internet (ex: do trabalho), o navegador exibe o aviso **"NÃO SEGURO"** porque a aplicação é servida via HTTP puro, sem criptografia TLS/SSL.

### Ambiente Atual
| Item             | Valor                         |
|------------------|-------------------------------|
| VPS              | Hostgator Brasil              |
| SO               | Ubuntu/Debian                 |
| Reverse Proxy    | Nginx                         |
| Domínio          | Nenhum (acesso por IP)        |
| Porta da App     | 8000 (Gunicorn/Uvicorn)       |
| Protocolo atual  | HTTP (inseguro)               |

---

## 2. Solução Proposta

Configurar **HTTPS com certificado SSL gratuito** usando:

- **DuckDNS** — domínio gratuito apontando para o IP da VPS
- **Let's Encrypt + Certbot** — certificado SSL gratuito com renovação automática
- **Nginx** — proxy reverso com terminação SSL

### Arquitetura Final

```
Internet (HTTPS:443)
    │
    ▼
  Nginx (SSL Termination)
    │
    ▼
  Gunicorn/Uvicorn (HTTP:8000, localhost only)
```

---

## 3. Pré-requisitos

- [ ] Acesso SSH à VPS
- [ ] IP público fixo da VPS (verificar com `curl ifconfig.me`)
- [ ] Portas 80 e 443 liberadas no firewall da VPS e no painel Hostgator

---

## 4. Passo a Passo

### 4.1 — Obter Domínio Gratuito (DuckDNS)

1. Acessar [https://www.duckdns.org](https://www.duckdns.org)
2. Fazer login com Google ou GitHub
3. Criar subdomínio, ex: `saa29.duckdns.org`
4. Informar o IP público da VPS
5. Salvar

> **Nota:** O DuckDNS oferece subdomínios gratuitos permanentes. Alternativas: FreeDNS, No-IP.

### 4.2 — Instalar Certbot

```bash
sudo apt update
sudo apt install -y certbot python3-certbot-nginx
```

### 4.3 — Configurar Nginx

Criar ou editar o arquivo de configuração do site:

```bash
sudo nano /etc/nginx/sites-available/saa29
```

Conteúdo:

```nginx
server {
    listen 80;
    server_name saa29.duckdns.org;  # Substituir pelo subdomínio escolhido

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Tamanho máximo de upload (ajustar conforme necessário)
    client_max_body_size 50M;
}
```

Ativar o site e testar:

```bash
sudo ln -sf /etc/nginx/sites-available/saa29 /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4.4 — Gerar Certificado SSL

```bash
sudo certbot --nginx -d saa29.duckdns.org
```

O Certbot irá:
- Validar a propriedade do domínio
- Obter o certificado SSL gratuito
- Configurar automaticamente o Nginx para HTTPS
- Adicionar redirecionamento HTTP → HTTPS

### 4.5 — Liberar Portas no Firewall

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
sudo ufw status
```

### 4.6 — Verificar Renovação Automática

```bash
sudo systemctl status certbot.timer
sudo certbot renew --dry-run
```

O certificado Let's Encrypt expira a cada **90 dias**, mas o Certbot renova automaticamente.

---

## 5. Validação

Após a configuração:

- [ ] Acessar `https://saa29.duckdns.org` — deve exibir cadeado verde 🔒
- [ ] Acessar `http://saa29.duckdns.org` — deve redirecionar para HTTPS
- [ ] Testar do computador do trabalho — deve funcionar sem aviso de segurança
- [ ] Verificar certificado: `curl -vI https://saa29.duckdns.org 2>&1 | grep -i "SSL\|certificate"`

---

## 6. Troubleshooting

| Problema | Solução |
|---|---|
| Certbot falha na validação | Verificar se portas 80/443 estão abertas e DNS aponta para o IP correto |
| Nginx não inicia | Executar `sudo nginx -t` para ver erros de sintaxe |
| Certificado expira | Verificar se `certbot.timer` está ativo |
| Erro 502 Bad Gateway | Verificar se a aplicação está rodando na porta 8000 |
| Timeout no acesso externo | Verificar firewall do painel Hostgator além do `ufw` |

---

## 7. Referências

- [Certbot - Instruções Nginx/Ubuntu](https://certbot.eff.org/instructions?ws=nginx&os=ubuntufocal)
- [DuckDNS](https://www.duckdns.org)
- [Let's Encrypt](https://letsencrypt.org)
- [Nginx Reverse Proxy Docs](https://docs.nginx.com/nginx/admin-guide/web-server/reverse-proxy/)

---

## 8. Scripts

O script automatizado está em [`setup_ssl.sh`](./setup_ssl.sh) nesta mesma pasta.  
**Revisar e adaptar o subdomínio antes de executar.**
