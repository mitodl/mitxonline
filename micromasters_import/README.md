MicroMasters Import
---

This is a temporary django app to faciliate the migration of MicroMasters data to MITx Online.

**NOTE:** it's important not to depend long term on any of the code or data models in this app as they will all probably be removed at a later date

#### Data Models

There are two data models that are designed to aid migration of MicroMasters data:

- `CourseId` - maps MicroMasters' `Course.id` values to `Course` objects in MITx Online
- `ProgramId` - maps MicroMasters' `Program.id` values to `Program` objects in MITx Online

The strategy we'll use here is to create records for each course and program in MicroMasters we want to import. The MicroMasters database will be mounted via [`postgres_fdw`](https://www.postgresql.org/docs/current/postgres-fdw.html) so that we can select/join across both databases. Then when the import queries run we'll join on these tables like this:

```sql
SELECT 
    run.title,
    run.edx_course_key,
    run.enrollment_url,
    run.start_date,
    run.end_date,
    run.enrollment_start,
    run.enrollment_end,
    course_ids.course_id
FROM foreign_data.courses_courserun as run
    JOIN public.micromasters_import_courseid as course_ids
        ON course_ids.micromasters_id = run.course_id
```