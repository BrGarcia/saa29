Você deve integrar o módulo de processamento de imagens em `app/shared/services/image/` ao projeto sem alterar a regra de negócio existente.

Contexto da arquitetura:
- `app/modules/` contém regras de negócio e casos de uso dos domínios.
- `app/shared/` contém serviços técnicos reutilizáveis entre módulos.
- O módulo de imagens já existe em `app/shared/services/image/` com os arquivos:
  - `pipeline.py`
  - `converter.py`
  - `resizer.py`
  - `optimizer.py`
  - `validator.py`

Objetivo da integração:
- Fazer com que qualquer fluxo de upload de imagem/anexo do sistema use `process_image()` antes de salvar o arquivo final.
- O módulo de imagens deve ser chamado pelos módulos de domínio, mas não deve conter conhecimento de negócio específico de nenhum módulo.

O que deve ser feito:
1. Identificar todos os pontos do sistema onde arquivos de imagem são recebidos ou salvos.
2. Antes do armazenamento definitivo, salvar o arquivo em uma área temporária (`var/tmp/` ou equivalente).
3. Chamar `app.shared.services.image.pipeline.process_image(temp_path)` para:
   - validar o arquivo
   - converter HEIC/HEIF quando necessário
   - redimensionar quando necessário
   - comprimir e gerar WebP
4. Salvar o caminho final retornado pelo pipeline no banco de dados ou no registro correspondente.
5. Remover o arquivo temporário somente após o processamento bem-sucedido.
6. Preservar o comportamento atual do sistema fora do fluxo de imagens.
7. Adicionar tratamento de erro para falha de validação, conversão, resize ou compressão.
8. Criar ou ajustar testes unitários e de integração para cobrir:
   - upload de JPG
   - upload de PNG
   - upload de HEIC/HEIF
   - arquivo inválido
   - arquivo muito grande
   - pipeline completo
9. Não mover lógica de negócio para `shared`.
10. Não alterar APIs públicas dos módulos sem necessidade.

Regras de implementação:
- O módulo `shared/services/image` deve permanecer genérico e reutilizável.
- Os módulos de negócio só devem chamar o pipeline.
- Não duplicar a lógica de processamento de imagem em outros lugares.
- Usar imports consistentes com a estrutura do projeto.
- Manter compatibilidade com Windows e Linux.

Pontos de integração esperados:
- Upload de anexos em panes
- Upload de imagens em aeronaves
- Upload de imagens em equipamentos
- Qualquer outro módulo que receba arquivos visuais

Critério de sucesso:
- O projeto passa a processar imagens automaticamente via `shared/services/image`.
- O código fica desacoplado e reutilizável.
- Nenhuma regra de negócio é quebrada.
- Os testes relevantes continuam passando.