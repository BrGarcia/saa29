# Plano de Implementação: Processamento e Otimização de Imagens (IMGDIET)

**Status geral:** Etapas 1–3 concluídas. Etapas 4–5 em aberto (integração nos módulos de domínio).

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
- [x] Validar ambiente local/docker com as novas bibliotecas.

### Etapa 2: Validação e Testes Unitários (TDD - Concluído)
- [x] Criar testes unitários em `tests/unit/shared/services/image/`.
- [x] Validar `validator.py`, `converter.py`, `resizer.py`, `optimizer.py` e `pipeline.py`.
- [x] Garantir que o pipeline limpa arquivos temporários corretamente (`test_process_image_cleans_up_temp_directory`: verifica que o `TemporaryDirectory` criado pelo pipeline é removido do disco após a execução).

### Etapa 3: Refinamento do Pipeline (Concluído)
- [x] Ajustar `app/shared/services/image/pipeline.py` para lidar com buffers em memória (`bytes`) além de arquivos em disco.
- [x] Implementar uso de `tempfile.TemporaryDirectory` para isolamento total e cleanup garantido.
- [x] Atualizar `validator.py` para validar buffers diretamente via `io.BytesIO`.
- [x] Validar que o pipeline retorna `bytes` quando o input é `bytes`, facilitando a integração com serviços de storage.

### Etapa 4: Integração no Módulo de Panes
- [ ] Local: `app/modules/panes/service.py` -> função `upload_anexo`.
- [ ] **Mudança**: Antes de chamar `storage_svc.upload`, os `arquivo_bytes` devem passar pelo `pipeline.process_image`.
- [ ] **Lógica de Fallback**: Caso o processamento falhe, decidir se o sistema deve aceitar o original (com aviso) ou rejeitar o upload.

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
1. Iniciar a **Integração no Módulo de Panes (Etapa 4)**.
2. Configurar o **Processamento em Background (Etapa 5)** para manter a agilidade da UI.

## 6. Estado Atual da Implementação (2026-05-02)

| Componente | Arquivo | Status |
|---|---|:---:|
| Dependências | `requirements.txt` | ✅ |
| Constantes de config | `app/bootstrap/config/image.py` | ✅ |
| Validador | `app/shared/services/image/validator.py` | ✅ |
| Conversor HEIC | `app/shared/services/image/converter.py` | ✅ |
| Redimensionador | `app/shared/services/image/resizer.py` | ✅ |
| Otimizador (imgdiet) | `app/shared/services/image/optimizer.py` | ✅ |
| Pipeline principal | `app/shared/services/image/pipeline.py` | ✅ |
| Testes unitários | `tests/unit/shared/services/image/` | ✅ |
| Integração em Panes | `app/modules/panes/service.py` | ⏳ |
| Processamento em background | `app/modules/panes/router.py` | ⏳ |
