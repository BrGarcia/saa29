# ALGORITHM_SPECS.md  
**Especificação de Algoritmos – Sistema de Gestão de Panes (Eletrônica A-29)**

## 1. Visão Geral

Este documento descreve os fluxos lógicos e algoritmos principais do sistema, incluindo criação, atualização e conclusão de panes.

---

## 2. Fluxo de Autenticação

### Algoritmo: Login

1. Receber username e senha
2. Buscar usuário no banco
3. Comparar senha com hash armazenado
4. Se válido:
   - Criar sessão autenticada
   - Redirecionar para a página principal de panes
5. Se inválido:
   - Retornar erro

---

## 3. Fluxo de Criação de Pane

### Algoritmo: Nova Pane

1. Usuário clica em "Nova Pane"
2. Exibir matriz de icones 5x5 com aeronaves (59XX)
3. Usuário seleciona aeronave
4. Perguntar: deseja anexar imagem?
   - Se SIM:
     - Abrir upload
     - Armazenar imagem
   - Se NÃO:
     - Continuar fluxo
5. Exibir campo de descrição
6. Se descrição vazia:
   - Definir como "AGUARDANDO EDICAO"
7. Criar registro:
   - status = ABERTA
   - data_abertura = NOW()
   - criado_por = usuário logado
8. Salvar no banco
9. Redirecionar para a página de panes

---

## 4. Fluxo de Visualização

### Algoritmo: Visualizar Pane

1. Usuário clica na pane
2. Buscar dados completos
3. Buscar anexos
4. Exibir tela detalhada

---

## 5. Fluxo de Atualização

### Algoritmo: Editar Pane

1. Usuário altera descrição
2. Validar conteúdo
3. Atualizar registro no banco
4. Registrar timestamp

---

## 6. Fluxo de Upload de Imagem

### Algoritmo: Upload

1. Receber arquivo
2. Validar tipo (jpg, png)
3. Validar tamanho
4. Gerar nome único
5. Armazenar (local ou cloud)
6. Registrar no banco (tabela anexos)

---

## 7. Fluxo de Conclusão de Pane

### Algoritmo: Concluir Pane

1. Usuário clica em "Concluir"
2. Verificar se já está resolvida
3. Atualizar:
   - status = RESOLVIDA
   - data_conclusao = NOW()
   - concluido_por = usuário logado
4. Salvar alterações
5. Atualizar a listagem operacional de panes

---

## 8. Regras de Status

Estados possíveis:
- ABERTA
- RESOLVIDA

### Transições permitidas:
- ABERTA → RESOLVIDA

---

## 9. Algoritmo de Cores

if status == "ABERTA":
    cor = vermelho

if status == "RESOLVIDA":
    cor = verde

---

## 10. Filtros

### Algoritmo: Filtrar Panes

1. Receber parâmetros:
   - texto
   - status
   - aeronave
   - data
2. Construir query dinâmica
3. Executar busca
4. Retornar lista filtrada

---

## 11. Validações Gerais

- Campos obrigatórios devem ser verificados
- Inputs sanitizados
- Upload protegido contra arquivos maliciosos

---

## 12. Logs (Futuro)

- Registrar ações:
  - criação
  - edição
  - conclusão
- Armazenar:
  - usuário
  - timestamp
  - ação realizada
