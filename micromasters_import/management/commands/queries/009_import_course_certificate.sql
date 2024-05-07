--- import DEDP course certificates for users who have mitxonline account in MicroMaster:
----Since the certificate from MM is per course, it picks the courseRun with highest grade to create certificate for
----It also utilizes the mapping table to get the certificate page revision

----There are two CTEs
--- The first one is to compute the highest grades learner get per course
--- Then find out which course run matches with highest grade since the goal is to pick the run with the highest grade
WITH highest_dedp_course_grade AS (
    SELECT
        grade.user_id,
        run.course_id,
        MAX(grade.grade) AS max_grade
    FROM public.courses_courserungrade AS grade
    JOIN public.courses_courserun AS run
        ON grade.course_run_id = run.id
    JOIN public.micromasters_import_courseid AS course_map --- Use mapping table to ensure we only count DEDP courses
        ON run.course_id = course_map.course_id
    GROUP BY grade.user_id, run.course_id
),
highest_grade_courserun AS (
    SELECT
        grade.user_id,
        grade.course_run_id,
        run.course_id
    FROM public.courses_courserungrade AS grade
    JOIN public.courses_courserun AS run
        ON grade.course_run_id = run.id
    JOIN highest_dedp_course_grade AS highest_grade
        ON (run.course_id = highest_grade.course_id
        AND grade.user_id = highest_grade.user_id
        AND grade.grade = highest_grade.max_grade)
)
INSERT INTO public.courses_courseruncertificate(
   created_on,
   updated_on,
   uuid,
   is_revoked,
   course_run_id,
   user_id,
   certificate_page_revision_id
)
SELECT
   mm_certificate.created_on,
   mm_certificate.updated_on,
   uuid(mm_certificate.hash),
   false AS is_revoked,
   highest_grade_courserun.course_run_id,
   highest_grade_courserun.user_id,
   certificate_map.certificate_page_revision_id
FROM micromasters.grades_micromasterscoursecertificate AS mm_certificate
JOIN micromasters.social_auth_usersocialauth AS mm_social
   ON mm_certificate.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
   ON mm_social.uid = mo_user.username
JOIN public.micromasters_import_courseid AS course_pk_map
   ON mm_certificate.course_id = course_pk_map.micromasters_id
JOIN highest_grade_courserun
   ON course_pk_map.course_id = highest_grade_courserun.course_id
   AND mo_user.id = highest_grade_courserun.user_id
JOIN public.micromasters_import_coursecertificaterevisionid AS certificate_map --It maps each DEDP course to a 'current' certificate template
   ON highest_grade_courserun.course_id = certificate_map.course_id
WHERE mm_social.provider = 'mitxonline'
ON CONFLICT DO NOTHING;
