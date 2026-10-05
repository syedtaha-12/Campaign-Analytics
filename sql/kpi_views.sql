-- KPI views for the Customer Campaign dashboard.
-- Each view answers one business question. Power BI reads these directly.
-- conversion_rate = % of contacted customers who subscribed.

-- 1. Headline numbers
CREATE OR REPLACE VIEW v_kpi_summary AS
SELECT
    COUNT(*)                                        AS total_contacts,
    SUM(subscribed)::int                            AS total_subscribed,
    ROUND(100.0 * AVG(subscribed), 2)               AS conversion_rate_pct,
    ROUND(AVG(campaign), 2)                         AS avg_calls_per_customer,
    ROUND(AVG(call_minutes)::numeric, 2)            AS avg_call_minutes,
    ROUND(100.0 * AVG(contacted_before), 2)         AS pct_contacted_before
FROM campaign_contacts;

-- 2. Which age groups respond best?
CREATE OR REPLACE VIEW v_by_age_group AS
SELECT
    age_group,
    COUNT(*)                            AS contacts,
    SUM(subscribed)::int                AS subscribed,
    ROUND(100.0 * AVG(subscribed), 2)   AS conversion_rate_pct
FROM campaign_contacts
GROUP BY age_group
ORDER BY age_group;

-- 3. Which jobs respond best? (customer segment)
CREATE OR REPLACE VIEW v_by_job AS
SELECT
    job,
    COUNT(*)                            AS contacts,
    SUM(subscribed)::int                AS subscribed,
    ROUND(100.0 * AVG(subscribed), 2)   AS conversion_rate_pct
FROM campaign_contacts
GROUP BY job
ORDER BY conversion_rate_pct DESC;

-- 4. Campaign activity by month
CREATE OR REPLACE VIEW v_by_month AS
SELECT
    month_num,
    INITCAP(month)                      AS month,
    COUNT(*)                            AS contacts,
    SUM(subscribed)::int                AS subscribed,
    ROUND(100.0 * AVG(subscribed), 2)   AS conversion_rate_pct
FROM campaign_contacts
GROUP BY month_num, month
ORDER BY month_num;

-- 5. Does calling someone more times help? (engagement)
CREATE OR REPLACE VIEW v_by_calls AS
SELECT
    CASE WHEN campaign >= 6 THEN '6+' ELSE campaign::text END  AS calls_this_campaign,
    COUNT(*)                                                    AS contacts,
    ROUND(100.0 * AVG(subscribed), 2)                           AS conversion_rate_pct
FROM campaign_contacts
GROUP BY 1
ORDER BY MIN(campaign);

-- 6. Did past campaign results predict this one?
CREATE OR REPLACE VIEW v_by_previous_outcome AS
SELECT
    poutcome                            AS previous_outcome,
    COUNT(*)                            AS contacts,
    ROUND(100.0 * AVG(subscribed), 2)   AS conversion_rate_pct
FROM campaign_contacts
GROUP BY poutcome
ORDER BY conversion_rate_pct DESC;

-- 7. Cell phone vs landline
CREATE OR REPLACE VIEW v_by_contact AS
SELECT
    contact                             AS contact_type,
    COUNT(*)                            AS contacts,
    ROUND(100.0 * AVG(subscribed), 2)   AS conversion_rate_pct
FROM campaign_contacts
GROUP BY contact;
