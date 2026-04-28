# security_summary

controls:
- jwt_access_token
- persisted_refresh_token_with_rotation
- token_blacklist_on_logout
- csrf_middleware
- rate_limit_login
- account_lockout_after_failed_attempts
- trusted_host
- cors_restricted
- security_headers_and_csp
- upload_type_and_size_validation
- local_or_r2_storage_abstraction

transport_rules:
- api_auth: Authorization_Bearer_supported
- web_auth: cookie_saa29_token_supported
- token_read_order: header_then_cookie

upload_rules:
- allowed_ext: jpg,jpeg,png,pdf,doc,docx
- block_path_traversal: true
- validate_real_type: true

sensitive_env:
- APP_SECRET_KEY
- DEFAULT_ADMIN_PASSWORD
- R2_ACCESS_KEY_ID
- R2_SECRET_ACCESS_KEY

security_docs:
- docs/SECURITY.md
- docs/development/cloudflare_r2.md
- docs/api/referencia-api.md

files_of_interest:
- app/modules/auth/security.py
- app/modules/auth/router.py
- app/bootstrap/dependencies.py
- app/shared/middleware/csrf.py
- app/shared/core/file_validators.py
- app/shared/core/storage.py
- app/shared/core/limiter.py

reporting:
- do_not_open_public_issue_for_vuln
- follow_docs_SECURITY_md

recent_actions:
- 2026-04-28: Full Frontend CSP Hardening (removed all inline scripts and event handlers).
- 2026-04-27: External security audit completed (docs/relatorio/revisao_claude.md).
- 2026-04-27: Critical issues C-01 (CSRF bypass) and C-02 (Cookie secure flag) resolved.
