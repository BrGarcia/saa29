# security_summary

controls:
- jwt_access_token
- persisted_refresh_token_with_rotation
- refresh_token_family_revocation_on_reuse
- token_blacklist_on_logout
- csrf_middleware
- rate_limit_login_and_search
- account_lockout_after_failed_attempts
- trusted_host
- cors_restricted
- strict_csp_script_src_self_no_inline
- upload_type_and_size_validation
- zip_slip_path_containment_validation
- zip_bomb_ratio_and_entry_limit_validation
- single_flight_upload_lock
- local_or_r2_storage_abstraction
- bcrypt_sha256_pre_hash_protection

transport_rules:
- api_auth: Authorization_Bearer_supported
- web_auth: cookie_saa29_token_supported
- token_read_order: header_then_cookie

upload_rules:
- allowed_ext: jpg,jpeg,png,pdf,doc,docx,zip
- block_path_traversal: true
- validate_real_type: true
- validate_zip_security: true

sensitive_env:
- APP_SECRET_KEY
- DEFAULT_ADMIN_PASSWORD
- R2_ACCESS_KEY_ID
- R2_SECRET_ACCESS_KEY

security_docs:
- docs/guides/SECURITY.md
- docs/guides/cloudflare_r2.md
- docs/guides/sugestao_envio.md
- docs/architecture/referencia-api.md
- docs/architecture/RBAC.md

files_of_interest:
- app/modules/auth/security.py
- app/modules/auth/router.py
- app/bootstrap/dependencies.py
- app/shared/middleware/csrf.py
- app/shared/core/file_validators.py
- app/shared/core/storage.py
- app/shared/core/limiter.py
- app/modules/publicacoes/router.py
- app/modules/inspecoes/router.py

reporting:
- do_not_open_public_issue_for_vuln
- follow_docs_SECURITY_md

recent_actions:
- 2026-05-01: Inspections module fully integrated, migrated and active. Endpoints secured with CurrentUser and EncarregadoOuAdmin.
- 2026-05-01: Created RBAC.md matrix to consolidate user roles and permissions documentation.
- 2026-05-07: Added token reuse protection, fixed storage error masking, secured inventory RBAC.
- 2026-05-27: Added length constraint to calendar event notes, active inspections checks on toggle manual aircraft status, and manual magic bytes fallback for file validators.
- 2026-07-25: Refactored CSRFMiddleware (app/shared/middleware/csrf.py) to prevent token desynchronization on GET binary/file downloads (PDF/CSV/XLSX/images).
- 2026-08-08: Implemented Zip-Slip path containment and Zip Bomb limits in `scripts/publicacoes/publicar.py` for publication archive uploads.
- 2026-08-08: Secured `_resolver_pdf` path traversal in `app/modules/publicacoes/router.py` with `is_relative_to` containment check against test fixtures directory.
- 2026-08-08: Enforced single-flight lock on `PublicacoesUploadJob` preventing concurrent worker execution.
- 2026-08-08: Resolved timezone-aware vs timezone-naive datetime comparison bug in `calendario/service.py:get_events`.
- 2026-08-08: Merged `feature/modulo-publicacoes` into `development` with 100% test coverage (650+ tests passing).
