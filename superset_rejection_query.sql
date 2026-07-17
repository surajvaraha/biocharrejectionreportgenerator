-- ============================================================================
-- Biochar Rejection Report — Superset dataset query
-- ============================================================================
-- Run this in Superset SQL Lab against the CHARIFY connection (charify_prod), then
-- "Save dataset". Export the result as .xlsx and upload it into the Rejection Report
-- Generator tool to produce the partner PDFs.
--
-- The tool is fully offline: every column it needs (including partner_name) is
-- produced here. It never connects to a database.
--
-- Notes:
--   * partner_name is resolved via the postgres_fdw foreign table
--     `foreign_production.organizations` (points at the production/accounts DB).
--     charify only stores facilities.organization_id.
--   * Filter is status = 'REJECTED' only. The misspelled enum value 'REJECETD'
--     exists in the type definition but no rows use it.
--   * ref_sub_type LIKE 'ArtisanalProcess%' keeps it to batch-kiln process media
--     (biochar_media is shared across sites/biomass/etc.).
--   * image_url uses the no-auth media stream endpoint (returns the JPEG directly).
--   * Date filtering: add a Superset time-range filter on `validated_at`
--     (validation date), `production_start` (production date), or the new
--     `batch_created_at` (when the batch_kiln row itself was created).
--   * `batch_created_at` is exported so it can be paired with the separate
--     "Validation Tasks" dataset (see superset_task_query.sql) — the task table
--     lives in MasterService's DB (Regen backend), not charify_prod, so it can't
--     be joined here in one query. Export both sheets and merge them in the
--     report generator tool (it accepts an optional second "Tasks" file).
-- ============================================================================

SELECT
    org.name                AS partner_name,          -- via foreign_production.organizations
    f.organization_id       AS organization_id,
    f.name                  AS facility_name,
    f.state                 AS facility_state,
    f.district              AS facility_district,
    bk.id                   AS batch_kiln_id,
    bk.cycle_id             AS cycle_id,
    k.name                  AS kiln_name,
    bk.status               AS batch_status,
    bk.created_at           AS batch_created_at,
    c.batch_start_time      AS production_start,
    c.batch_end_time        AS production_end,
    m.id                    AS media_id,
    m.ref_sub_type          AS stage_code,
    CASE m.ref_sub_type
        WHEN 'ArtisanalProcessMoisture'        THEN 'Wood Moisture'
        WHEN 'ArtisanalProcessPreStart'        THEN 'Pre-Start'
        WHEN 'ArtisanalProcessStart'           THEN 'Process Start'
        WHEN 'ArtisanalProcessMiddle'          THEN 'Process Middle'
        WHEN 'ArtisanalProcessEnd'             THEN 'Process End'
        WHEN 'ArtisanalProcessPostQuenching'   THEN 'Post-Quenching'
        WHEN 'ArtisanalProcessQuenchingVideo'  THEN 'Quenching Video'
        WHEN 'ArtisanalProcessBiocharSampling' THEN 'Biochar Sampling'
        ELSE m.ref_sub_type
    END                     AS stage,
    m.verification_remarks  AS rejection_reason,
    m.last_verified_by      AS validated_by,
    m.last_verified_at      AS validated_at,
    'https://charify.varahaag.in/api/v1/media/stream/'
        || m.ref_id || '/' || m.ref_sub_type || '/' || m.id   AS image_url
FROM batch_kilns bk
JOIN cycle          c   ON bk.cycle_id = c.id
JOIN facilities     f   ON c.facility  = f.id
JOIN kilns          k   ON bk.kiln_id  = k.id
JOIN biochar_media  m   ON m.ref_id    = bk.id
LEFT JOIN foreign_production.organizations org ON org.id = f.organization_id
WHERE bk.is_active = TRUE
  AND m.is_archive = FALSE
  AND m.status = 'REJECTED'
  AND m.ref_sub_type LIKE 'ArtisanalProcess%'
ORDER BY partner_name, bk.id, m.ref_sub_type, m.id;
