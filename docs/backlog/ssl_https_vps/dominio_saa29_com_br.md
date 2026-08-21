# Configuração do Domínio saa29.com.br

> **Status:** 🚧 Em execução — etapa 1 (DNS) pendente de ação no painel registro.br
> **Data:** 2026-08-21
> **Substitui:** o plano DuckDNS descrito em [`README.md`](./README.md), agora obsoleto

---

## 1. Situação atual (verificada em 2026-08-21)

| Item | Estado |
|---|---|
| Domínio | `saa29.com.br` registrado no registro.br |
| Nameservers | `a.auto.dns.br` / `b.auto.dns.br` (DNS automático do registro.br) |
| Registro A de `saa29.com.br` | **ausente** — não resolve para IP nenhum |
| Registro A de `www.saa29.com.br` | **ausente** (NXDOMAIN) |
| IP da VPS | `143.95.216.54` (Hostgator, SSH na porta `22022`) |
| Protocolo atual | HTTP puro, acesso por IP |

O domínio está registrado e delegado, mas **a zona não tem registros**. Nada aponta
para a VPS ainda. Este é o bloqueio da etapa 1.

Comando usado para verificar:

```bash
nslookup -type=NS saa29.com.br 8.8.8.8
nslookup -type=A  saa29.com.br 8.8.8.8
```

---

## 2. Etapa 1 — Criar os registros DNS no registro.br

Esta etapa é manual, no painel do registro.br. Não há API pública para isso no
plano padrão.

1. Acessar [https://registro.br](https://registro.br) e entrar na conta
2. Ir em **Meus Domínios → saa29.com.br → Editar Zona DNS**
   (o domínio usa o *DNS automático*, então a zona é editável pelo próprio painel)
3. Adicionar os dois registros:

| Nome | Tipo | Dados | TTL |
|---|---|---|---|
| *(vazio / `@`)* | `A` | `143.95.216.54` | 3600 |
| `www` | `A` | `143.95.216.54` | 3600 |

> **Por que dois `A` e não um `CNAME` para o `www`:** o registro.br aceita ambos,
> mas o `A` duplicado evita a cadeia extra de resolução e mantém os dois nomes
> simétricos para o certbot, que valida cada um separadamente.

4. Salvar e aguardar a propagação (o registro.br costuma publicar em minutos;
   o TTL de 3600 vale para caches externos)

### Validação da etapa 1

```bash
dig +short A saa29.com.br      @8.8.8.8   # deve retornar 143.95.216.54
dig +short A www.saa29.com.br  @8.8.8.8   # idem
```

**Só avance para a etapa 2 quando os dois comandos retornarem o IP da VPS.**
O Let's Encrypt limita a 5 falhas de validação por hora por domínio — tentar o
certbot antes do DNS propagar queima essa cota.

---

## 3. Etapa 2 — Nginx + certificado SSL na VPS

Script pronto: [`setup_dominio_saa29.sh`](./setup_dominio_saa29.sh)

```bash
scp -P 22022 docs/backlog/ssl_https_vps/setup_dominio_saa29.sh usuario@143.95.216.54:~
ssh -p 22022 usuario@143.95.216.54
chmod +x setup_dominio_saa29.sh
sudo ./setup_dominio_saa29.sh
```

O script: valida o DNS, instala o certbot, escreve o virtual host do Nginx,
libera o firewall, emite o certificado para `saa29.com.br` + `www.saa29.com.br`
com redirect HTTP→HTTPS, e confirma a renovação automática.

### ⚠️ Diferença crítica em relação ao `setup_ssl.sh` antigo

O script anterior executava `ufw allow 22/tcp` e em seguida `ufw enable` sem
confirmação. **Esta VPS usa SSH na porta 22022**, não na 22. Rodar aquele script
aqui ativaria o firewall sem liberar a porta certa e cortaria o acesso SSH à
máquina, sem caminho de volta pela rede.

O `setup_dominio_saa29.sh` corrige isso: libera `${SSH_PORT}` (22022) antes de
qualquer ativação e só ativa o `ufw` com confirmação explícita.

---

## 4. Etapa 3 — Ajustar a aplicação para o novo domínio

Depois do certificado emitido, o `.env` **da VPS** precisa de três mudanças.
Sem elas o domínio responde, mas a sessão fica insegura.

```dotenv
ALLOWED_HOSTS=saa29.com.br,www.saa29.com.br
ALLOWED_ORIGINS=https://saa29.com.br,https://www.saa29.com.br
FORCE_SECURE_COOKIES=true
```

Depois:

```bash
cd ~/saa29 && docker-compose down && docker-compose up -d --build
```

### Por que cada uma importa

- **`ALLOWED_HOSTS`** — `app/bootstrap/main.py:124` só registra o
  `TrustedHostMiddleware` quando o valor **não** é `*`. Hoje o padrão em
  `app/bootstrap/config/__init__.py:152` é `["*"]`, então o middleware nem sobe e
  qualquer `Host` é aceito. Definir a lista explicitamente fecha o vetor de
  Host header injection. Note que `localhost`, `127.0.0.1` e `testserver` já são
  acrescentados pelo próprio código — não precisam entrar no `.env`.

- **`ALLOWED_ORIGINS`** — o CORS roda com `allow_credentials=True`, o que proíbe
  `*` pela especificação. O código detecta isso e cai num fallback de
  `localhost` (`main.py:145`), registrando um warning. Ou seja: em produção com
  `*`, o CORS de fato **rejeita o próprio domínio**. Precisa ser explícito, e com
  o esquema `https://`.

- **`FORCE_SECURE_COOKIES`** — hoje está `false` no `.env`. Enquanto o acesso era
  HTTP puro isso era coerente; com HTTPS ativo, mantê-lo `false` deixa o cookie
  de sessão sem o atributo `Secure`, ou seja, sujeito a vazar numa requisição
  HTTP. Vira `true` junto com o certificado, não depois.

### Cabeçalhos de proxy — não requer mudança

O `gunicorn_conf.py` não define `forwarded_allow_ips`, mas o padrão do Gunicorn
é `127.0.0.1` e o Nginx faz o proxy do mesmo host. O `X-Forwarded-Proto` enviado
pelo virtual host é, portanto, aceito, e a aplicação enxerga o esquema `https`
corretamente. Nenhum ajuste necessário.

---

## 5. Validação final

- [ ] `https://saa29.com.br` abre com cadeado
- [ ] `https://www.saa29.com.br` abre com cadeado
- [ ] `http://saa29.com.br` redireciona para HTTPS
- [ ] Login funciona e o cookie de sessão tem `Secure` + `HttpOnly`
      (DevTools → Application → Cookies)
- [ ] Upload de publicação acima de 10 MB passa (limite do Nginx: 50 MB)
- [ ] `sudo certbot renew --dry-run` sem erro

---

## 6. Pendências conhecidas

- O `README.md` desta pasta descreve o caminho DuckDNS e ficou obsoleto com a
  compra do domínio. Vale marcá-lo como superado em vez de apagar — o
  troubleshooting de Nginx/certbot da seção 6 continua válido.
- O e-mail de notificação do Let's Encrypt está vazio no script (`EMAIL=""`).
  Sem ele não há aviso caso a renovação automática quebre. Preencher antes de
  rodar.
