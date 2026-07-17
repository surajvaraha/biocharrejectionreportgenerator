-- ============================================================================
-- Biochar Rejection Report — Validation Tasks dataset query
-- ============================================================================
-- Run this in Superset SQL Lab against the "PostgreSQL" connection (id=1, which
-- reaches MasterService's `production` DB — the Regen/Dhara backend), then
-- "Save dataset". Export alongside the main rejection dataset
-- (superset_rejection_query.sql) and upload BOTH into the Rejection Report
-- Generator tool — it merges them on batch_kiln_id = ref_id.
--
-- Why a separate query/connection:
--   `task` lives in MasterService's Django DB, not charify_prod. charify creates
--   one "Batch Kiln Validation" task per batch_kiln once its cycle completes AND
--   all required media is uploaded — whichever happens last. This means a batch
--   produced on day X may not get its task created until several days later
--   (task_created_at ~ "when all the images actually arrived"), so filtering by
--   task creation/due date surfaces a different — and often more operationally
--   relevant — population than filtering by production/batch-created date.
--
-- Notes:
--   * project_id = 3 scopes this to the ARTISANAL_PRODUCTION_BATCH task type
--     charify creates (see pkg/master_service_connection/task.go in Kalki-Backend).
--   * ref_id = charify's batch_kilns.id. NOT a local FK — there is no
--     cross-database join available (no FDW/DuckDB bridge between charify_prod
--     and production), so this dataset is exported and merged separately.
--   * task_status is the review-workflow status (NOT_STARTED/IN_PROGRESS/
--     COMPLETED/CANCELLED/BLOCKED/FAILED) — a work-item status, NOT the
--     accept/reject verdict. Keep using batch_kilns.status for that.
--   * created_on (not created_at) is the task's creation timestamp.
--   * Date filtering: add Superset time-range filters on `task_created_at` and/or
--     `task_due_date`.
-- ============================================================================

SELECT
    id                       AS task_id,
    ref_id                   AS batch_kiln_id,
    task_status              AS task_status,
    created_on               AS task_created_at,
    due_date                 AS task_due_date,
    completion_date          AS task_completion_date
FROM public.task
WHERE project_id = 3
ORDER BY ref_id;
