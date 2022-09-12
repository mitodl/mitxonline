----This script is to migrate the grades for course run from MicroMaster:
----  It computes score from FinalGrade and ProctoredExamGrade using formula - course run grade * 0.4 + exam grade * 0.6
----  grades need to exist in both FinalGrade (course run) and ProctoredExamGrade (exam)
----  grades need to be 'passed'

WITH courses_have_exam AS (
    SELECT
        DISTINCT mm_examrun.course_id
    FROM micromasters.exams_examrun AS mm_examrun
    JOIN micromasters.courses_course AS mm_course
        ON mm_examrun.course_id = mm_course.id
),
 --- this is to compute the best grade learner gets for the course runs they have enrolled
best_courserun_grades AS (
    SELECT
        mm_grade.user_id,
        mm_grade.course_run_id,
        MAX(mm_grade.grade) AS max_grade
    FROM micromasters.grades_finalgrade AS mm_grade
    JOIN micromasters.courses_courserun AS mm_courserun
        ON mm_grade.course_run_id = mm_courserun.id
    JOIN courses_have_exam
        ON mm_courserun.course_id = courses_have_exam.course_id
    WHERE mm_grade.status = 'complete'
      AND mm_grade.passed = True
    GROUP BY mm_grade.user_id, mm_grade.course_run_id
),
--- this is to compute the best exam grades learner get for every course run in the exam they signed up for
best_exam_grades AS (
    SELECT
        mm_exam_grade.user_id,
        mm_exam_grade.course_id,
        mm_courserun.id AS course_run_id,
        MAX(mm_exam_grade.score) AS max_score
    FROM micromasters.grades_proctoredexamgrade AS mm_exam_grade
    JOIN micromasters.courses_courserun AS mm_courserun
       ON mm_exam_grade.course_id = mm_courserun.course_id
    JOIN courses_have_exam
       ON mm_exam_grade.course_id = courses_have_exam.course_id
    WHERE mm_exam_grade.passed = true
    GROUP BY mm_exam_grade.user_id, mm_courserun.id, mm_exam_grade.course_id
),
combined_final_grades AS (
    SELECT
        best_grade.user_id,
        best_grade.course_run_id,
        ROUND(CAST(best_grade.max_grade * 100 * 0.4 + best_exam.max_score * 0.6 AS numeric), 1) AS calculated_grade,
        mm_courserun.course_id,
        mm_courserun.edx_course_key,
        mm_grade.created_on,
        mm_grade.updated_on,
        True AS passed  -- because both course run and exam are passed
    FROM best_courserun_grades AS best_grade
    JOIN best_exam_grades AS best_exam
       ON (best_grade.course_run_id = best_exam.course_run_id
           AND best_grade.user_id = best_exam.user_id)
    JOIN micromasters.courses_courserun AS mm_courserun
       ON best_grade.course_run_id = mm_courserun.id
    --- The following joins are to get the corresponding passed and metadate fields matched with previous aggregated CTEs
    JOIN micromasters.grades_finalgrade AS mm_grade
       ON (best_grade.course_run_id = mm_grade.course_run_id
           AND best_grade.user_id = mm_grade.user_id
           AND best_grade.max_grade = mm_grade.grade)
    JOIN micromasters.grades_proctoredexamgrade AS mm_exam
       ON (best_exam.course_id = mm_exam.course_id
           AND best_exam.user_id = mm_exam.user_id
           AND best_exam.max_score = mm_exam.score)
)

INSERT INTO public.courses_courserungrade(
   created_on,
   updated_on,
   passed,
   grade,
   letter_grade,
   set_by_admin,
   course_run_id,
   user_id
)
SELECT
  combined_grades.created_on,
  combined_grades.updated_on,
  combined_grades.passed,
  combined_grades.calculated_grade,
  CASE
      WHEN combined_grades.calculated_grade >= 82.5 THEN 'A'
      WHEN combined_grades.calculated_grade >= 65 THEN 'B'
      WHEN combined_grades.calculated_grade >= 55 THEN 'C'
      WHEN combined_grades.calculated_grade >= 50 THEN 'D'
      ELSE 'F'
  END AS letter_grade,
  False AS set_by_admin,
  mo_courserun.id,
  mo_user.id
FROM combined_final_grades AS combined_grades
JOIN public.courses_courserun AS mo_courserun
    ON combined_grades.edx_course_key = mo_courserun.courseware_id
JOIN micromasters.social_auth_usersocialauth AS mm_social
    ON combined_grades.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
    ON mm_social.uid = mo_user.username
WHERE mm_social.provider = 'mitxonline'
ON CONFLICT DO NOTHING;