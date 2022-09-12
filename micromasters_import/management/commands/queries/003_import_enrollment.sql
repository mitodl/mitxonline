--courserun Enrollment migration from MicroMaster to MITxOnline
-- Limit to those who have taken exam and passed
INSERT INTO public.courses_courserunenrollment(
    run_id,
    user_id,
    change_status,
    active,
    edx_enrolled,
    edx_emails_subscription,
    enrollment_mode,
    created_on,
    updated_on)
SELECT
    DISTINCT
    mo_courserun.id,
    mo_user.id,
    '' AS change_status,
    (mm_enrollment.data->>'is_active')::boolean,
    true,
    false,
    mm_enrollment.data->>'mode',
    coalesce(((mm_enrollment.data->'course_details'->>'enrollment_start')::timestamp), now()),
    coalesce(((mm_enrollment.data->'course_details'->>'enrollment_end')::timestamp), now())
FROM micromasters.dashboard_cachedenrollment AS mm_enrollment
JOIN micromasters.courses_courserun AS mm_courserun
  ON mm_enrollment.course_run_id = mm_courserun.id
JOIN micromasters.grades_proctoredexamgrade AS mm_exam
  ON mm_courserun.course_id = mm_exam.course_id
 AND mm_enrollment.user_id = mm_exam.user_id
JOIN micromasters.social_auth_usersocialauth AS mm_social
  ON mm_enrollment.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
  ON mm_social.uid = mo_user.username
JOIN public.courses_courserun AS mo_courserun
  ON mm_courserun.edx_course_key = mo_courserun.courseware_id
WHERE mm_social.provider = 'mitxonline'
  AND mm_exam.passed = True
ON CONFLICT DO NOTHING;
