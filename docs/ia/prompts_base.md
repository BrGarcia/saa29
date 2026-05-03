# prompt_templates

prompt_project_context:
> Use docs/ia first for low-token context. If any conflict exists, prefer docs/README.md, docs/architecture/, docs/core/, docs/guides/, docs/backlog/ and docs/SECURITY.md.

prompt_file_summary:
> Summarize the file in max 5 lines using keys: role, inputs, outputs, deps, risks.

prompt_module_scan:
> For this module, return only: paths, entities, endpoints, rules, tests, risks.

prompt_api_change:
> Compare the endpoint behavior against docs/architecture/referencia-api.md and return only mismatches, missing tests and required doc updates.

prompt_arch_review:
> Check whether code still follows router->service->orm layering. Return only violations, with paths.

prompt_security_review:
> Check auth, csrf, uploads, token flow and env handling. Return only concrete risks and affected files.

prompt_docs_sync:
> Update docs/ia summaries after official docs are updated. Keep delta-only, machine-friendly, no prose.

prompt_db_safety:
> Before any database change, assume the current database is in active use, preserve all existing pane records, create a backup of the original database first, and never reset or reseed the active database.

prompt_inspecoes_isolation:
> When working on app/modules/inspecoes, keep it isolated unless activation is explicitly requested. Do not register its router, import its models in bootstrap, add migrations, alter shared enums, or modify active frontend navigation without explicit approval.

prompt_inspecoes_activation:
> To activate inspections, plan the sequence explicitly: backup active DB, create migration, import models in bootstrap, include router under a chosen prefix, bind frontend routes/templates, add tests, then update docs/architecture and docs/ia.

prompt_frontend_csp:
> CRITICAL: This project uses a strict Content-Security-Policy (script-src 'self'). NEVER use inline scripts (`<script>...</script>`) or inline event handlers (e.g., `onclick="..."`) in HTML templates. ALWAYS use `addEventListener` in external `.js` files. To pass data from Jinja to JS, use `<meta name="...">` or `data-*` attributes on HTML elements, then read them in JS.
