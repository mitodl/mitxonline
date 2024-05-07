-- Import program certificates from MicroMaster to MITxOnline
-- Mapping table - micromasters_import_programid need to be populated before running this query
INSERT INTO public.courses_programcertificate(
   uuid,
   user_id,
   program_id,
   certificate_page_revision_id,
   is_revoked,
   created_on,
   updated_on)
SELECT
   uuid(mm_certificate.hash),
   mo_user.id,
   pk_map.program_id,
   pk_map.program_certificate_revision_id,
   false AS is_revoked,
   mm_certificate.created_on,
   mm_certificate.updated_on
FROM micromasters.grades_micromastersprogramcertificate AS mm_certificate
JOIN public.micromasters_import_programid AS pk_map
  ON mm_certificate.program_id = pk_map.micromasters_id
JOIN micromasters.social_auth_usersocialauth AS mm_social
  ON mm_certificate.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
  ON mm_social.uid = mo_user.username
WHERE mm_social.provider = 'mitxonline'
ON CONFLICT DO NOTHING;
