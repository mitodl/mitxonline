--courserun migration from MicroMaster to MITxOnline
INSERT INTO public.courses_courserun(
    title,
    courseware_id,
    run_tag,
    courseware_url_path,
    start_date,
    end_date,
    enrollment_start,
    enrollment_end,
    expiration_date,
    live,
    created_on,
    updated_on,
    course_id,
    is_self_paced)
SELECT
    mm_courserun.title,
    mm_courserun.edx_course_key,
    (regexp_match(mm_courserun.edx_course_key, '[^(+|/)]+$'))[1],
    mm_courserun.enrollment_url,
    mm_courserun.start_date,
    mm_courserun.end_date,
    mm_courserun.enrollment_start,
    mm_courserun.enrollment_end,
    mm_courserun.end_date + INTERVAL '1 day', -- expiration date must be later than end_date per validation
    true, --live
    coalesce(mm_courserun.enrollment_start, now()),
    coalesce(mm_courserun.enrollment_end, now()),
    pk_map.course_id,
    false  -- self_paced
FROM micromasters.courses_courserun AS mm_courserun
JOIN public.micromasters_import_courseid AS pk_map
  ON mm_courserun.course_id = pk_map.micromasters_id
LEFT JOIN public.courses_courserun AS mo_courserun
  ON mo_courserun.courseware_id = mm_courserun.edx_course_key
WHERE mm_courserun.is_discontinued = false
  AND mm_courserun.courseware_backend = 'edxorg'
  AND mo_courserun.courseware_id IS NULL ---course runs that don't exist in MITxOnline
ON CONFLICT DO NOTHING;
