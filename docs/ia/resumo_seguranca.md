# Resumo de Seguranca

critical:
- .env nao deve ir para Git
- uploads nao devem ficar misturados ao codigo
- logs e bancos locais devem ficar fora da raiz operacional
- dados sensiveis nao devem entrar em docs publicas

controls:
- CSRF ativo em fluxos de formulario e api
- rate limit e account lockout
- tokens com rotacao de refresh
- validacao de magic bytes para anexos
- uso de cookies/headers conforme fluxo do frontend

reporting:
- vulnerabilidades devem seguir docs/SECURITY.md
- nao abrir issue publica para falhas de seguranca

files_of_interest:
- app/auth/security.py
- app/middleware/csrf.py
- app/core/file_validators.py
- app/core/storage.py
- app/core/limiter.py

