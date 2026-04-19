# Relatório de Auditoria de Código SAA29

## Overview
Auditoria de código realizada no ambiente SAA29. O sistema utiliza **FastAPI**, **SQLAlchemy (Async)** e **SQLite**, com integração a templates **Jinja2**. A estrutura geral do banco de dados demonstra maturidade em tipagem forte e modelagem (ORMs bem definidos), além de gestão de criptografia de senhas seguindo as melhores práticas (`bcrypt`). A principal fragilidade identificada reside no alto acoplamento de algumas regras de negócio (God Services) e potenciais falhas de desempenho (consultas N+1) em listagens assíncronas complexas.

## Critical Findings
- **[app/equipamentos/service.py:192]** (e múltiplos outros) - *Risco de N+1 Queries:* Faltam opções robustas como `selectinload` em joins condicionais ou listagens de inventário pesadas. O carregamento *lazy* de objetos vinculados em loops assíncronos causa queda severa de performance ou erros `MissingGreenlet`.
- **[app/equipamentos/service.py:270]** - *Violação do Princípio SRP:* A função de ajuste e movimentação de inventário concentra criação de itens, invalidação de slots, checagem de conflitos e *rollback* manual de dependências cruzadas (God Function), dificultando a manutenção isolada.

## Security
- **OWASP A01 (Broken Access Control):** Os endpoints utilizam injeção de dependência (`CurrentUser`, `EncarregadoOuAdmin`) de forma consistente nos roteadores. As rotas estão devidamente protegidas pelo `app/auth/security.py`.
- **OWASP A02 (Cryptographic Failures):** A verificação e o hash de senhas (`_pwd_context = CryptContext(schemes=["bcrypt"])`) estão corretos. O limite de 72 caracteres imposto nas funções de hash e verify mitiga ataques de exaustão de CPU (DoS por bcrypt).
- **OWASP A03 (Injection):** Não foram encontrados usos diretos de concatenação de string em SQL ou `text()` desprotegido. O uso do construtor `select()` e tipagem em variáveis `uuid` previne SQL Injection. Os templates Jinja2 não expõem renderização `| safe` deliberada de dados inseguros (XSS prevenido por padrão).
- **Data Protection:** Senhas iniciais (`DEFAULT_ADMIN_PASSWORD`) em `init_db.py` são carregadas do ambiente e sofrem hash imediato antes de persistirem.

## Performance
- **Bottlenecks Assíncronos:** Diversas junções (joins) no histórico retornam grandes conjuntos de dados que atualmente estão sendo limitados com `limit(15)`, o que ajuda, mas a falta de paginação real (Offset/Keyset) no banco de dados pode estrangular a interface gráfica conforme o sistema escalar.
- **Resource Leaks:** O sistema gere as conexões adequadamente através da `asynccontextmanager` via FastAPI Dependency Injection, assegurando fechamento automático das sessões assíncronas do SQLAlchemy sem vazar cursores abertos do SQLite.

## Duplication
- **Boilerplate de Consultas:** Queries que buscam o `Usuário` ativo por ID repetem-se nos serviços de autenticação, de panes e de equipamentos.
- **Padrões de Resposta:** Blocos `try/except ValueError` nos routers (`router.py`) capturam mensagens literais de erro vindas dos services. É recomendada a criação de exceções customizadas de domínio (ex: `InventarioConflitoError`) para centralizar as mensagens HTTP 409 e 404.

## Architecture
- **Padrões de Design (SOLID):**
  - O projeto respeita a separação Router -> Service -> Model.
  - Há violações da *Dependency Inversion Principle* (DIP): os serviços interagem puramente com classes do SQLAlchemy em vez de interfaces ou repositórios, o que amarra a lógica de negócios irremediavelmente ao ORM e dificulta testes unitários por *mocks*.
  - Acoplamento Estrutural: O domínio `equipamentos` sabe demais sobre os domínios `aeronaves` e `auth` a nível de junções e lógica cruzada.

## Improvements
- **Resiliência do Banco:** O `app/database.py` configura PRAGMAs para o SQLite (`foreign_keys=ON`). Pode-se aumentar a eficiência global de concorrência assegurando que `journal_mode=WAL` seja habilitado junto ao pool connection.
- **Tratamento de Exceções Baseado em Domínio:** Substituir `raise ValueError("Item não encontrado")` por uma `DomainException` gerenciada num *Global Exception Handler* do FastAPI.

## Refactor
1. **app/equipamentos/service.py** (Correção de Query N+1)
```python
# ANTES (Exemplo de problema)
res = await db.execute(select(Instalacao))

# DEPOIS (Mitigação para listagens pesadas)
res = await db.execute(
    select(Instalacao).options(selectinload(Instalacao.item))
)
```

2. **app/equipamentos/service.py** (Desacoplamento de Serviço)
Criar uma camada de `InventarioValidator` isolada para limpar funções gigantes, movendo validações repetitivas de slots vazios ou restrições de instalação para fora da lógica de gravação no banco de dados.

## Checklist
- [x] OWASP Vulnerability Check
- [x] Injection Validation (SQL, Command, Jinja)
- [x] Auth and JWT Mechanism Scan
- [x] N+1 Queries Identifier
- [x] Architecture Layering Assessment
- [ ] Implementação de Testes Unitários Baseados em Domínio (Cobertura)
