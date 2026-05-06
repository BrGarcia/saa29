# Workflow: Merge Main (SAA29)
meta:
- purpose: automated_deploy_logic
- truth: docs/methodology/merge_main.md
- trigger: "realize branch conforme merge_main.md"

steps:
1: Preparation
- git add .
- git commit -m "feat/fix: <msg>"
- git push origin <current_branch>

2: Integration (Development)
- git checkout development
- git pull origin development
- git merge <previous_branch>
- git push origin development

3: Safety Checks
- check_migrations: migrations/versions/
- check_r2: env STORAGE_BACKEND=r2
- run_tests: pytest

4: Production (Main)
- git checkout main
- git pull origin main
- git merge development
- git push origin main

post_deploy:
- monitor_railway_logs: scripts/start.sh (R2 restore check)
- check_alembic: alembic upgrade head success
- verify_data_persistence: UI check

rules:
- NO_R2_NO_MERGE: Fail if R2 connection is suspect.
- PERSISTENCE: sqlite is ephemeral; R2 is the only truth.
- GLOBAL: Always git push after git commit.
