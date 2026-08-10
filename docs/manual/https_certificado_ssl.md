# HTTPS e Certificado SSL/TLS em VPS

Este guia explica como remover a mensagem **"Nao Seguro"** do navegador apos publicar o SAA29 em uma VPS.

## Por que aparece "Nao Seguro"

O navegador mostra essa mensagem quando o sistema esta sendo acessado por **HTTP** ou quando o **HTTPS** esta mal configurado.

Para o site ser considerado seguro, ele precisa responder por:

```text
https://seudominio.com.br
```

e possuir um certificado SSL/TLS valido.

## Requisitos

Antes de emitir o certificado, confira:

1. Voce possui um dominio, por exemplo `saa29.seudominio.com.br`.
2. O dominio aponta para o IP publico da VPS no DNS.
3. As portas `80` e `443` estao liberadas no firewall da VPS e no painel do provedor.
4. Existe um servidor web recebendo trafego externo, normalmente **Nginx** ou **Apache**.
5. A aplicacao esta rodando corretamente na VPS, mesmo que ainda por HTTP.

> Observacao: certificados publicos normalmente sao emitidos para dominios, nao para acesso direto por IP.

## Caminho recomendado com Let's Encrypt

O caminho mais comum e gratuito e usar o **Let's Encrypt** com o **Certbot**.

### Usando Nginx

Em servidores Ubuntu/Debian com Nginx:

```bash
sudo apt update
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br
```

Durante o processo, escolha a opcao de redirecionar HTTP para HTTPS, se o Certbot perguntar.

Depois disso, acesse:

```text
https://seudominio.com.br
```

### Usando Apache

Em servidores Ubuntu/Debian com Apache:

```bash
sudo apt update
sudo apt install certbot python3-certbot-apache
sudo certbot --apache -d seudominio.com.br -d www.seudominio.com.br
```

## Quando o projeto roda com Docker

Se o SAA29 estiver rodando com Docker Compose, o mais comum e deixar o container da aplicacao em uma porta interna, por exemplo `3000`, `5173`, `8000` ou `8080`, e colocar o Nginx na frente como proxy reverso.

Exemplo conceitual:

```text
Internet -> Nginx HTTPS :443 -> aplicacao Docker em porta interna
```

Nesse caso, o certificado fica no Nginx, nao diretamente no container da aplicacao.

## Checklist de DNS

No painel DNS do seu dominio, crie ou confira os registros:

```text
Tipo A
Nome: @
Valor: IP_PUBLICO_DA_VPS

Tipo A
Nome: www
Valor: IP_PUBLICO_DA_VPS
```

Se estiver usando subdominio:

```text
Tipo A
Nome: saa29
Valor: IP_PUBLICO_DA_VPS
```

Depois de alterar DNS, pode levar alguns minutos ou horas para propagar.

## Checklist de firewall

Na VPS, libere as portas HTTP e HTTPS:

```bash
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw status
```

Tambem confira o firewall do painel do provedor da VPS, pois alguns provedores bloqueiam portas antes do trafego chegar ao servidor.

## Renovacao do certificado

Certificados Let's Encrypt vencem periodicamente, mas o Certbot normalmente configura a renovacao automatica.

Para testar:

```bash
sudo certbot renew --dry-run
```

Se esse comando terminar sem erro, a renovacao automatica tende a funcionar.

## Problemas comuns

- **O navegador continua mostrando "Nao Seguro"**: confirme se esta acessando `https://` e nao `http://`.
- **Certbot falha na validacao**: confira se o DNS aponta para a VPS correta e se a porta `80` esta aberta.
- **HTTPS abre, mas a aplicacao nao carrega**: confira a configuracao de proxy reverso do Nginx/Apache.
- **Erro de certificado para www**: emita o certificado incluindo tanto `seudominio.com.br` quanto `www.seudominio.com.br`, se ambos forem usados.
- **Acesso por IP continua "Nao Seguro"**: use o dominio configurado no certificado.

## Resumo

Para deixar o SAA29 seguro na internet:

1. Aponte um dominio para a VPS.
2. Configure Nginx ou Apache como entrada publica.
3. Emita um certificado gratuito com Let's Encrypt/Certbot.
4. Redirecione HTTP para HTTPS.
5. Confirme renovacao automatica do certificado.

