# Backlog Item 8.3: Ajuste Fino de Fallback do python-magic

## 1. Descrição do Problema
O validador de arquivos de upload exige a biblioteca `python-magic`, que depende dos binários nativos `libmagic` do sistema operacional. Em containers Docker alpinistas e ambientes serverless minimalistas, a ausência de libmagic gera erros críticos impedindo o upload de qualquer arquivo válido.

## 2. Plano de Implementação
1. **Atualizar Dockerfile:** Adicionar a instalação da dependência `libmagic` no `Dockerfile` da aplicação (usando `apt-get install -y libmagic1` para imagens base Debian/Ubuntu ou `apk add file` para Alpine).
2. **Implementar fallback seguro de validação:** No validador (`app/shared/core/file_validators.py`), implementar uma validação alternativa por assinatura de cabeçalho de arquivo (magic bytes manuais para assinaturas PNG, JPG, PDF) caso a importação de `magic` falhe ou o binário não esteja instalado.
3. **Logar fallback:** Emitir aviso estruturado (`WARNING`) informando que o validador está operando em modo de compatibilidade básica por falta de libmagic.

## 3. Critérios de Aceitação
* Uploads de arquivos legítimos funcionam normalmente dentro do container Docker minimalista de produção.
* A ausência física de `libmagic` na máquina hospedeira não resulta em erro 500 no backend.
* O sistema de fallback barra assinaturas de arquivos adulterados (ex: executáveis renomeados para `.png`).
