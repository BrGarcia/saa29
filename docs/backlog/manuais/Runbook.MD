# Runbook — Implantação e Operação do Sistema de Manuais EMB-314

> Terceiro documento do planejamento. [Projeto.MD](Projeto.MD) = arquitetura;
> [Especificacao.MD](Especificacao.MD) = comportamento; **este documento = como colocar
> no ar, manter no ar e recuperar de falhas.** Escrito para ser seguido por qualquer
> pessoa da equipe (ou por você mesmo daqui a um ano), passo a passo, sem conhecimento
> prévio do projeto.

**Data:** 03/08/2026 · **Versão:** 1.0
**Pendências que este runbook referencia:** D-02 (autenticação) e D-04 (provedor/domínio) — ver Especificacao.MD §10. Onde aparecer `manuais.exemplo.com.br`, substituir pelo domínio real quando D-04 for resolvida.

---

## 1. Visão da Infraestrutura

```
Internet ──► DNS (manuais.exemplo.com.br)
                │
        VPS Linux (1 vCPU, 1 GB RAM, 20 GB NVMe)
                │
        Docker Compose
        ├── caddy    : portas 80/443, TLS automático, serve /data/* estático
        └── app      : FastAPI/Uvicorn na porta interna 8000
                │
        Volumes no host:
        /srv/manuais/data/     ← PDFs (~3 GB)
        /srv/manuais/index/    ← catalog.db (~2 GB)
        /srv/manuais/caddy/    ← certificados TLS
```

Requisitos da VPS (mínimo): 1 vCPU, 1 GB RAM, 20 GB de disco (preferir NVMe — ver risco
"disco lento" em Especificacao.MD §11), Ubuntu 24.04 LTS ou Debian 12.

---

## 2. Provisionamento Inicial da VPS (uma única vez)

### 2.1 Acesso e endurecimento básico
```bash
# como root, logo após criar a VPS
adduser deploy
usermod -aG sudo deploy
rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy   # copia a chave SSH

# SSH: desabilitar root e senha
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/'       /etc/ssh/sshd_config
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
systemctl restart ssh

# firewall: só SSH e web
apt update && apt install -y ufw
ufw allow OpenSSH && ufw allow 80/tcp && ufw allow 443/tcp
ufw --force enable

# atualizações de segurança automáticas
apt install -y unattended-upgrades
dpkg-reconfigure -plow unattended-upgrades
```

### 2.2 Docker
```bash
curl -fsSL https://get.docker.com | sh
usermod -aG docker deploy
```

### 2.3 Estrutura de diretórios no host
```bash
sudo mkdir -p /srv/manuais/{data,index,caddy}
sudo chown -R deploy:deploy /srv/manuais
```

### 2.4 DNS
Criar registro `A` do domínio (D-04) apontando para o IP da VPS **antes** do primeiro
`docker compose up` — o Caddy precisa disso para emitir o certificado TLS.

---

## 3. Arquivos de Implantação (versionados no repositório)

### 3.1 `docker-compose.yml` (referência)
```yaml
services:
  app:
    build: .
    restart: unless-stopped
    environment:
      - DATA_DIR=/data
      - INDEX_DIR=/index
      - ADMIN_TOKEN=${ADMIN_TOKEN}        # definir em .env — nunca commitar
    volumes:
      - /srv/manuais/data:/data:ro        # app só LÊ os PDFs
      - /srv/manuais/index:/index
    mem_limit: 512m                       # trava de segurança (alvo real: <200 MB)

  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - /srv/manuais/data:/srv/data:ro
      - /srv/manuais/caddy:/data
```

### 3.2 `Caddyfile` (referência)
```
manuais.exemplo.com.br {
    encode gzip

    handle_path /data/* {
        root * /srv/data
        file_server
        header Cache-Control "public, max-age=86400"
    }

    handle {
        reverse_proxy app:8000
    }
}
```
Notas: o Caddy emite e renova TLS sozinho; `file_server` já suporta `Range` requests
(requisito do PDF.js — Especificacao.MD E-11).

---

## 4. Primeiro Deploy

```bash
# na VPS, como deploy
git clone <URL_DO_REPOSITORIO> ~/supertucano-docs
cd ~/supertucano-docs
echo "ADMIN_TOKEN=$(openssl rand -hex 24)" > .env   # guardar este token no cofre da equipe
docker compose up -d --build
```

### 4.1 Carga inicial do acervo (~3 GB)
Do computador local (onde está o resultado do merge da Fase 0):
```bash
rsync -avz --progress ./data/ deploy@manuais.exemplo.com.br:/srv/manuais/data/
```
`rsync` é retomável — se a conexão cair, rodar de novo continua de onde parou.

### 4.2 Indexação inicial
```bash
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" https://manuais.exemplo.com.br/admin/reindex
# acompanhar (esperado: 15–60 min na primeira vez):
watch -n 30 'curl -s https://manuais.exemplo.com.br/api/status | python3 -m json.tool'
```

### 4.3 Checklist de validação do deploy
- [ ] `https://` abre com cadeado válido (TLS ok)
- [ ] Home lista os manuais por categoria com revisões
- [ ] Busca `sangria do compressor` → resultado abre na página exata (CA-01)
- [ ] `/api/status` mostra `documents` ≈ 12.100 e `index_state: idle`
- [ ] Um PDF grande abre no celular sem baixar o arquivo inteiro (testar em 4G)
- [ ] `docker stats` mostra app < 200 MB RSS (CA-06)

---

## 5. Operações de Rotina

### 5.1 Publicar/atualizar manuais (UC-04) — a operação mais frequente
```bash
# 1. copiar o manual novo (ou revisado) para o acervo
rsync -avz ./NOVO_MANUAL_1234/ deploy@manuais.exemplo.com.br:/srv/manuais/data/NOVO_MANUAL_1234/

# 2. disparar indexação incremental (segundos a poucos minutos)
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" https://manuais.exemplo.com.br/admin/reindex

# 3. conferir
curl -s https://manuais.exemplo.com.br/api/status | python3 -m json.tool
```
Remover manual = apagar a pasta de `/srv/manuais/data/` + reindexar (RN-09 remove do índice).

### 5.2 Atualizar a aplicação (novo release)
```bash
cd ~/supertucano-docs
git pull
docker compose up -d --build     # downtime ~2–5 s; aceitável para o perfil de uso
docker image prune -f            # limpar imagens antigas
```

### 5.3 Ver logs
```bash
docker compose logs -f app       # aplicação e indexador
docker compose logs -f caddy     # acessos e TLS
```

---

## 6. Backup e Restauração

### 6.1 O que proteger, e quanto dói perder

| Dado | Perda | Estratégia |
|---|---|---|
| `data/` (PDFs) | **Grave** — é o acervo | Cópia-mestre fora da VPS (a origem local já é o backup natural) + backup remoto |
| `index/catalog.db` | Leve — **reconstruível** por reindexação (< 1 h) | Backup diário por conveniência, não por necessidade |
| `.env` (ADMIN_TOKEN) | Leve — regenerável | Cofre de senhas da equipe |
| Repositório git | Leve | Já está no remoto (GitHub/GitLab) |

**Princípio: a VPS é descartável.** Tudo nela deve ser reconstruível a partir de:
repositório git + cópia-mestre de `data/` + este runbook.

### 6.2 Backup automático (na VPS)
```bash
# /etc/cron.daily/backup-manuais  (chmod +x)
#!/bin/sh
# snapshot íntegro do SQLite mesmo com app rodando (WAL-safe)
docker compose -f /home/deploy/supertucano-docs/docker-compose.yml \
  exec -T app sqlite3 /index/catalog.db ".backup /index/catalog-backup.db"
# enviar para armazenamento externo (definir destino junto com D-04; ex.: rclone p/ B2/S3)
rclone copy /srv/manuais/index/catalog-backup.db remoto:manuais-backup/
rclone sync  /srv/manuais/data/ remoto:manuais-data/   # incremental; só sobe o que mudou
```
Regra 3-2-1 simplificada: acervo existe (1) na origem local, (2) na VPS, (3) no
armazenamento remoto do backup.

### 6.3 Restauração completa (VPS nova, do zero)
Tempo estimado total: **~2 h**, dominado pelo upload do acervo.
1. Seções 2.1–2.4 (provisionamento) — ~20 min
2. Seção 4 (deploy + `.env` novo) — ~10 min
3. Restaurar acervo: `rclone copy remoto:manuais-data/ /srv/manuais/data/` (ou rsync da cópia-mestre)
4. Reindexar (seção 4.2) — ou restaurar `catalog-backup.db` para pular a espera
5. Rodar o checklist 4.3

---

## 7. Monitoramento

Proporcional ao porte do sistema — sem stack de observabilidade dedicada:

| O quê | Como | Alerta |
|---|---|---|
| Site no ar | Uptime Kuma (self-hosted em container, ~50 MB) ou UptimeRobot (SaaS grátis) monitorando `GET /api/status` | e-mail/Telegram se `down > 2 min` |
| Saúde do índice | O próprio `/api/status` (documents, last_index_run, db_size) | inspeção manual pós-publicação |
| Disco | `df -h /srv` — cron semanal mandando aviso se > 80% | e-mail |
| RAM/CPU | `docker stats` sob demanda; `mem_limit` do compose já impede runaway | — |

Decisão consciente: **não** instalar Prometheus/Grafana. Para um serviço, é peso sem retorno.

---

## 8. Diagnóstico de Problemas (triagem)

| Sintoma | Primeira verificação | Causa provável / ação |
|---|---|---|
| Site fora do ar | `docker compose ps` | Container parado → `docker compose up -d`; VPS reiniciou sem `restart: unless-stopped` aplicado |
| TLS inválido/expirado | `docker compose logs caddy \| grep -i acme` | DNS não aponta para a VPS; porta 80 bloqueada (o Caddy precisa dela para renovar) |
| Busca não encontra manual recém-publicado | `/api/status` → `last_index_run` | Esqueceram o passo 2 da seção 5.1 → reindexar |
| Busca lenta (> 1 s) | `docker stats` + `iostat -x 5` | Disco da VPS lento (risco documentado) ou indexação em curso ao mesmo tempo |
| PDF abre na página 1 em vez da página do resultado | Testar `#page=N` direto na URL | Regressão no viewer → checar CA-01 nos testes |
| Indexação travada (`index_state: running` há horas) | `docker compose logs app` | PDF patológico → E-02 deveria ter pulado; abrir issue com o caminho do arquivo logado; `docker compose restart app` destrava (lock é liberado no boot) |
| Erro 500 na busca | logs do app | Query não sanitizada (violação da RN-10) → bug, cobrir com teste |
| Disco cheio | `du -sh /srv/manuais/*` + `docker system df` | Imagens antigas → `docker image prune -f`; crescimento do acervo → planejar upgrade de disco |
| Acentuação quebrada em títulos | — | Violação da RN-07 (encoding) → bug no parser, não corrigir “no dado” |

Regra geral: **nunca editar `catalog.db` à mão.** Qualquer inconsistência de índice se
resolve com reindexação (é sempre seguro: o índice é 100% derivado de `data/`).

---

## 9. Segurança

- App roda como usuário não-root no container; `data/` montado **read-only** na app.
- Único endpoint mutante (`/admin/reindex`) exige `ADMIN_TOKEN` (e o resultado de D-02
  pode adicionar auth de leitura por cima).
- Caddy com TLS moderno por padrão; UFW fecha todo o resto; SSH só por chave.
- Sem banco exposto, sem portas extras: superfície de ataque = Caddy + app.
- Atualizações: `unattended-upgrades` no host; rebuild mensal das imagens
  (`docker compose build --pull`) para pegar patches de base.

## 10. Contatos e Convenções

| Papel | Quem | Observação |
|---|---|---|
| Dono do produto / acervo | Bruno (brunodog@gmail.com) | resolve D-01..D-05 |
| Operação da VPS | _definir_ | acesso SSH + cofre com ADMIN_TOKEN |
| Cofre de segredos | _definir_ (ex.: Bitwarden da equipe) | `.env`, chaves SSH, credenciais rclone |

**Convenções:** toda mudança de infra passa pelo git (Caddyfile, compose, este runbook);
o runbook é atualizado **na mesma PR** que muda o procedimento que ele descreve.
