# Plano de Implementação: Processamento e Otimização de Imagens (IMGDIET)

Este documento descreve o plano detalhado para integrar o serviço de processamento de imagens localizado em `app/shared/services/image` ao ecossistema do SAA29, com foco em eficiência de armazenamento, suporte a novos formatos (HEIC) e otimização automática.

## 1. Visão Geral do Módulo
O módulo é composto pelos seguintes componentes:
- `validator.py`: Garante a integridade e conformidade dos arquivos.
- `converter.py`: Converte formatos modernos/proprietários (HEIC/HEIF) para padrões web (JPG/PNG).
- `resizer.py`: Redimensiona imagens para limites pré-definidos (HD/Full HD), reduzindo o peso inicial.
- `optimizer.py`: Utiliza a biblioteca `imgdiet` para converter para WebP com compressão perceptiva (alvo PSNR 40).
- `pipeline.py`: Orquestra todas as etapas acima em um fluxo único.

## 2. Etapas de Implementação

### Etapa 1: Configuração e Dependências (Concluído)
- [x] Adicionar `Pillow`, `pillow-heif` e `imgdiet` ao `requirements.txt`.
- [x] Criar `app/bootstrap/config/image.py` com as constantes de limite (MAX_WIDTH, MAX_HEIGHT, TARGET_PSNR).

### Etapa 2: Refinamento do Pipeline
- [ ] Ajustar `app/shared/services/image/pipeline.py` para lidar com buffers em memória (`bytes`) além de arquivos em disco, para evitar I/O desnecessário antes da persistência final.
- [ ] Garantir que o `cleanup_intermediate_files` funcione corretamente em ambientes Docker (pastas temporárias).

### Etapa 3: Integração no Módulo de Panes
- [ ] Local: `app/modules/panes/service.py` -> função `upload_anexo`.
- [ ] **Mudança**: Antes de chamar `storage_svc.upload`, os `arquivo_bytes` devem passar pelo `pipeline.process_image`.
- [ ] **Lógica de Fallback**: Caso o processamento falhe, decidir se o sistema deve aceitar o original (com aviso) ou rejeitar o upload.

### Etapa 4: Integração no Módulo de Inspeções (Se aplicável)
- [ ] Verificar se há campos de evidência fotográfica nas tarefas de inspeção que se beneficiariam do pipeline.

### Etapa 5: Processamento em Background (Performance)
- [ ] Integrar com `fastapi.BackgroundTasks` no `router.py` de panes para que o usuário não precise esperar a otimização do `imgdiet` (que é intensiva em CPU) para receber a confirmação de upload.
- [ ] Implementar uma lógica de "placeholder" ou status de "processando" caso a imagem seja acessada imediatamente após o upload.

## 3. Benefícios Esperados
1. **Redução de Armazenamento**: Imagens WebP otimizadas podem ser até 80% menores que JPEGs originais de smartphones.
2. **Suporte a iPhones**: Conversão nativa de HEIC permite que mantenedores usem dispositivos Apple sem restrições.
3. **Performance de Carregamento**: Imagens redimensionadas para o tamanho da tela (Full HD) carregam instantaneamente no dashboard e detalhes de pane.
4. **Padronização**: Todo anexo de imagem no sistema será servido como `.webp`.

## 4. Riscos e Mitigações
- **Consumo de CPU**: `imgdiet` é pesado. **Mitigação**: Executar em background e monitorar o consumo nos containers Docker.
- **Perda de Qualidade**: Compressão agressiva. **Mitigação**: O alvo de PSNR 40 garante que a perda seja imperceptível ao olho humano.

## 5. Próximos Passos Imediatos
1. Criar testes unitários para o pipeline em `tests/unit/shared/services/image/`.
2. Realizar a primeira integração experimental no upload de anexos de Panes.
