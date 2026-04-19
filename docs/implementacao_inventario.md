# Plano de Implementação: Página de Inventário de Equipamentos

Este documento detalha o plano para criar a interface de inventário físico de
equipamentos por aeronave no SAA29, baseada na ficha de inventário (`docs/ficha_inventario.pdf`).

---

## 1. Objetivo

Criar uma nova página acessível pela barra superior de navegação onde o usuário pode:
1. **Visualizar** todos os equipamentos instalados em uma aeronave, com seus Part Numbers (PN), Serial Numbers (SN) e localização (compartimento).
2. **Filtrar** por matrícula da aeronave ou nome do equipamento.
3. **Registrar o campo REAL** — sincronizar o serial number fisicamente instalado com o sistema.

---

## 2. Estado Atual do Backend

> ✅ **O backend está 100% implementado e testado.**

| Camada | Arquivo | Status |
| :--- | :--- | :---: |
| **Modelos ORM** | `app/equipamentos/models.py` | ✅ Completo |
| **Schemas** | `app/equipamentos/schemas.py` | ✅ Completo |
| **Serviço** | `app/equipamentos/service.py` | ✅ Completo |
| **Router API** | `app/equipamentos/router.py` | ✅ Completo |
| Rota de Página | `app/pages/router.py` | ✅ Completo |
| Template HTML | `templates/inventario.html` | ✅ Funcional (Ajustes de UI em curso) |
| Ícone na Navbar | `templates/base.html` | ✅ Completo |

---

## 4. Modelo de Dados para Localização

O campo `sistema` da tabela `slots_inventario` é utilizado como **compartimento/localização**. Os valores seguem a nomenclatura técnica abreviada:

| Sigla | Localização Completa |
| :--- | :--- |
| `CEI` | Compartimento Eletrônico Inferior |
| `1P` | Posto Dianteiro (1P) |
| `2P` | Posto Traseiro (2P) |
| `CES` | Compartimento Eletrônico Superior |

---

## 5. Plano de Implementação (Status)

### Fase 1: Backend e API ✅
- Criado endpoint `GET /equipamentos/inventario/{aeronave_id}`.
- Criado endpoint `POST /equipamentos/inventario/ajuste` para sincronização de S/N.
- Implementada rastreabilidade precisa com `created_at` em `Instalacao`.

### Fase 2: Interface (UI) 🔄
- [✅] Criado template `inventario.html` com suporte a filtros e cores de status.
- [✅] Implementada coluna REAL com validação em tempo real.
- [✅] Implementado botão de sincronização (Sync) com lógica de transferência entre aeronaves.
- [🚀] **Próximo Ajuste:** Remover cabeçalhos de seção e transformar a Localização (Sigla) em uma coluna fixa na tabela.

### Fase 3: Navegação ✅
- Adicionado ícone de checklist na Navbar em `base.html`.
- Rota `/pages/inventario` configurada.

### Fase 4: Dados e Carga (Seed) ✅
- [✅] Atualizado `scripts/seed_equipamentos.py` com a lista técnica completa de 33 slots.
- [✅] Configurada aeronave **5916** como referência oficial de testes.

---

## 6. Evolução Futura

- **Persistência do campo REAL:** Criar coluna `serial_real` na tabela `instalacoes` para salvar o valor digitado pelo usuário, permitindo comparações históricas.
- **Exportação para PDF:** Gerar uma versão impressa da ficha de inventário no formato do PDF original.
- **Controle de Vencimentos na UI:** Adicionar badges de vencimento (OK/VENCENDO/VENCIDO) ao lado de cada item no inventário.

---

*Documento atualizado em 19 de abril de 2026.*
