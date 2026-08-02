

## 📋 Formato de Saída Obrigatório

Gere o diagnóstico organizando os achados rigorosamente no seguinte formato:

```markdown
### [Nº] [Título do Achado]
- **Severidade:** 🔴 Crítica | 🔴 Alta | 🟡 Média | 🟢 Baixa
- **Tipo:** Bug | Vulnerabilidade | Concorrência | Performance | Arquitetura
- **Evidência (`caminho/arquivo.py:Lxx`):** Código/trecho afetado.
- **Risco & Impacto:** O que falha em produção ou qual vulnerabilidade expõe.
- **Correção Recomendada:** Trecho refatorado ou plano de ação concreto.
```

---

## 🛑 Regras de Resposta


- **Sem enrolação ou elogios genéricos.** Seja direto, técnico e imparcial.
- **Cites exatos:** Sempre indique o arquivo e números de linha.
- **Priorização:** Agrupe por Severidade (🔴 Crítica/Alta ➔ 🟡 Média ➔ 🟢 Baixa) ao final com plano de ação em fases.
