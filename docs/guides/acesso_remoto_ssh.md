# Guia de Configuração — Acesso Remoto SSH via Tailscale (MacBook → Host Windows)

Este guia documenta o passo a passo para conectar remotamente um **MacBook** à máquina **Windows Host** onde o projeto **SAA29 (Antigravity)** está hospedado, utilizando **SSH** e **Tailscale**.

---

## 1. Informações da Máquina Host (Windows)

- **Usuário Host (Windows):** `brgar`
- **IP Tailscale (Host Windows):** `100.89.56.88`
- **Diretório do Projeto:** `C:\Users\brgar\Projetos\SAA29`
- **Porta HTTP Localhost:** `8000`

---

## 2. Pré-requisitos

1. **Tailscale** instalado e ativo em ambas as máquinas (MacBook e Windows) na mesma conta/tailnet.
2. **OpenSSH Server (`sshd`)** instalado e rodando no Windows Host (já configurado e ativo).

---

## 3. Passo a Passo no MacBook

### 3.1. Teste de Conexão Inicial via Terminal

No Terminal do MacBook, execute o comando abaixo para testar a comunicação SSH:

```bash
ssh brgar@100.89.56.88
```

Ao ser solicitado, digite a senha da conta do usuário `brgar` no Windows.

---

### 3.2. Configuração de Chave SSH (Autenticação Sem Senha)

Para evitar a necessidade de digitar a senha em cada conexão e garantir uma experiência fluida com extensões do editor:

1. **Gere o par de chaves no MacBook** (caso ainda não possua):
   ```bash
   ssh-keygen -t ed25519 -C "macbook-antigravity"
   ```
   *(Pressione Enter para aceitar os caminhos padrões)*.

2. **Copie a chave pública para o Host Windows**:
   ```bash
   ssh-copy-id brgar@100.89.56.88
   ```

> **Método Alternativo (Manual):**  
> Caso o comando `ssh-copy-id` falhe no ambiente Windows, abra a chave pública no Mac (`cat ~/.ssh/id_ed25519.pub`), copie o texto e adicione em uma nova linha do arquivo `C:\Users\brgar\.ssh\authorized_keys` no Windows.

---

### 3.3. Ajuste de Permissões de Administrador no Windows (Se necessário)

No Windows OpenSSH, por padrão, se o usuário `brgar` pertence ao grupo de **Administradores**, a chave SSH é procurada em `C:\ProgramData\ssh\administrators_authorized_keys`.

Se a autenticação por chave falhar para o usuário administrador:

1. Abra o arquivo `C:\ProgramData\ssh\sshd_config` no Windows com um editor de texto como Administrador.
2. Comente as duas linhas finais adicionando `#`:
   ```sshd_config
   # Match Group administrators
   #       AuthorizedKeysFile __PROGRAMDATA__/ssh/administrators_authorized_keys
   ```
3. Reinicie o serviço SSH no PowerShell (como Administrador):
   ```powershell
   Restart-Service sshd
   ```

---

## 4. Conectando via VS Code / Antigravity / Cursor no MacBook

1. No MacBook, abra o **VS Code** (ou Antigravity).
2. Instale a extensão **Remote - SSH** (`ms-vscode-remote.remote-ssh`).
3. Pressione `Cmd + Shift + P` e escolha **Remote-SSH: Connect to Host...**
4. Insira a string de conexão:
   ```text
   brgar@100.89.56.88
   ```
5. Após o estabelecimento da sessão remota, clique em **Open Folder** e selecione:
   ```text
   C:\Users\brgar\Projetos\SAA29
   ```

---

## 5. Acessando a Aplicação Web Rodando no Host

Quando o projeto for executado no Windows Host (`docker compose up` ou `python scripts/run_app.py` na porta `8000`), você pode acessá-lo no navegador do MacBook das seguintes formas:

- **Via IP do Tailscale:** [http://100.89.56.88:8000](http://100.89.56.88:8000)
- **Via Port Forwarding (no VS Code Remote-SSH):** Encaminhe a porta `8000` remota para a porta `8000` local e acesse via [http://localhost:8000](http://localhost:8000).
