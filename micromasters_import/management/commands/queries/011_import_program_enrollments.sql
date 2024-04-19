-- Import DEDP program enrollments from MicroMaster to MITxOnline
INSERT INTO public.courses_programenrollment(
    program_id,
    user_id,
    change_status,
    enrollment_mode,
    active,
    created_on,
    updated_on)
SELECT
    pk_map.program_id,
    mo_user.id,
    '' AS change_status,
    'audit', -- audit for now
    true,
    NOW(),
    NOW()
FROM micromasters.dashboard_programenrollment AS mm_enrollment
JOIN micromasters.courses_program AS mm_program
  ON mm_enrollment.program_id = mm_program.id
JOIN micromasters.social_auth_usersocialauth AS mm_social
  ON mm_enrollment.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
  ON mm_social.uid = mo_user.username
JOIN public.micromasters_import_programid AS pk_map
  ON mm_enrollment.program_id = pk_map.micromasters_id
WHERE mm_social.provider = 'mitxonline'
ON CONFLICT DO NOTHING;
