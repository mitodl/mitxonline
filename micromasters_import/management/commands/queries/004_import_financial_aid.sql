INSERT INTO public.flexiblepricing_flexibleprice(
    created_on,
    updated_on,
    status,
    income_usd,
    original_income,
    original_currency,
    country_of_income,
    date_exchange_rate,
    date_documents_sent,
    justification,
    country_of_residence,
    user_id,
    cms_submission_id,
    courseware_content_type_id,
    courseware_object_id,
    tier_id)
SELECT
    mm_aid.created_on,
    mm_aid.updated_on,
    CASE
         WHEN mm_aid.status IN ('docs-sent', 'pending-docs') THEN 'pending-manual-approval'
         ELSE mm_aid.status
    END,
    mm_aid.income_usd,
    mm_aid.original_income,
    mm_aid.original_currency,
    mm_aid.country_of_income,
    mm_aid.date_exchange_rate,
    mm_aid.date_documents_sent,
    mm_aid.justification,
    mm_aid.country_of_residence,
    mo_user.id,
    null AS cms_submission_id, -- there is no CMS submission for imported record
    mo_pricetier.courseware_content_type_id,  -- this refers to course program's content type id
    mo_pricetier.courseware_object_id,  -- this refers to program id on MITxOnline
    pk_map.flexible_price_tier_id
FROM micromasters.financialaid_financialaid AS mm_aid
JOIN micromasters.financialaid_tierprogram AS mm_tierprogram
    ON mm_aid.tier_program_id = mm_tierprogram.id
JOIN micromasters.financialaid_tier AS mm_tier
    ON mm_tierprogram.tier_id = mm_tier.id
JOIN micromasters.social_auth_usersocialauth AS mm_social
    ON mm_aid.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
    ON mm_social.uid = mo_user.username
JOIN public.micromasters_import_programtierid AS pk_map  -- There should be only DEDP program tier mappings
    ON mm_aid.tier_program_id = pk_map.micromasters_tier_program_id
JOIN public.flexiblepricing_flexiblepricetier AS mo_pricetier
    ON pk_map.flexible_price_tier_id = mo_pricetier.id
WHERE mm_tierprogram.current = true  -- only bring in current tier program
   AND mm_aid.status IN ('auto-approved', 'approved', 'created', 'docs-sent','pending-docs', 'pending-manual-approval')
   AND mm_social.provider = 'mitxonline'
ON CONFLICT DO NOTHING;
