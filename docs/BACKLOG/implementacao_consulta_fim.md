# Especificação Técnica: Consulta Rápida FIM (Fault Isolation Manual)

Este documento descreve o plano de implementação do módulo de consulta de procedimentos de falha baseados no manual FIM da aeronave.

## 1. Objetivo
Permitir que o mantenedor encontre rapidamente o procedimento técnico de correção a partir de uma mensagem de falha (ex: "ADC 001") exibida nos sistemas da aeronave.

## 2. Estrutura de Dados
O sistema utilizará os ativos existentes na pasta `docs/fim/`:
*   **Mapeamento:** `fim.json` - Contém a lista de objetos `{"mensagem": "...", "procedimento": "..."}`.
*   **Arquivos:** Documentos PDF nomeados seguindo o padrão `FIM1741_{procedimento}-.PDF`.

## 3. Arquitetura Proposta

### A. Backend (FastAPI)
*   **Novo Módulo:** `app/modules/fim/`.
*   **Endpoints:**
    *   `GET /fim/search?q=TERMO`: Realiza busca parcial por mensagens no arquivo JSON.
    *   `GET /fim/procedure/{code}`: Retorna os metadados do procedimento e o link para o arquivo.
*   **Serviço Estático:** Configurar o FastAPI para servir arquivos da pasta `docs/fim/` via rota protegida (ex: `/static/fim/`).

### B. Frontend (Desktop e Mobile)
*   **Interface de Busca:** Campo de entrada com busca em tempo real (debounce) que exibe resultados em uma lista.
*   **Visualizador:**
    *   Ao clicar no resultado, abrir o PDF em uma nova aba ou em um modal com o `<iframe>` do PDF nativo do navegador.
    *   Interface otimizada para mobile com botões grandes de "Abrir Manual".

## 4. Fluxo do Usuário
1.  O usuário acessa o menu "Consulta FIM" (ou atalho no Mobile).
2.  Digita o código ou nome da falha vista na aeronave.
3.  O sistema filtra instantaneamente as opções no `fim.json`.
4.  O usuário clica no resultado desejado.
5.  O sistema localiza o arquivo correspondente na pasta física e abre o manual técnico.

## 5. Regras e Restrições
*   **Segurança:** Apenas usuários autenticados podem acessar a busca e os arquivos PDF.
*   **Performance:** Carregar o JSON em memória (cache) ao iniciar o sistema para que as buscas sejam instantâneas.
*   **Robustez:** Caso o código no JSON não possua um arquivo PDF correspondente na pasta, o sistema deve exibir um aviso amigável.

## 6. Integrações Futuras
*   Vincular a busca do FIM diretamente na tela de "Registrar Pane". Se a descrição da pane bater com um código FIM, sugerir a abertura do manual automaticamente.
