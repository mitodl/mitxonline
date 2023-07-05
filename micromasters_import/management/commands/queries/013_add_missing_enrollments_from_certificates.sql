----This script is to add missing DEDP course enrollments for the imported MicroMasters data
----For MM, enrollments could be deleted from dashboard_cachedenrollment if users unenroll.
--- It need to be ran after 009_import_course_certificate

INSERT INTO public.courses_courserunenrollment(
    run_id,
    user_id,
    change_status,
    active,
    edx_enrolled,
    edx_emails_subscription,
    enrollment_mode,
    created_on,
    updated_on
)
SELECT
    certificate.course_run_id
    , certificate.user_id
    , ''
    , true
    , true
    , false
    , 'verified'
    , certificate.created_on
    , certificate.updated_on
FROM public.courses_courseruncertificate as certificate
LEFT JOIN public.courses_courserunenrollment as enrolled
      ON certificate.course_run_id = enrolled.run_id
      AND certificate.user_id = enrolled.user_id
WHERE enrolled.run_id IS NULL
ON CONFLICT DO NOTHING;