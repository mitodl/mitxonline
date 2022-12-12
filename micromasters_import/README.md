MicroMasters Import
---

This is a temporary django app to faciliate the migration of MicroMasters data to MITx Online.

**NOTE:** it's important not to depend long term on any of the code or data models in this app as they will all probably be removed at a later date

#### Data Models

There are a few data models that are designed to aid migration of MicroMasters data:

- `CourseId` - maps MicroMasters' `Course.id` values to `Course` objects in MITx Online
- `ProgramId` - maps MicroMasters' `Program.id` values to `Program` objects in MITx Online
- `ProgramTierId` - maps MicroMasters' `TierProgram.id` values to `FlexiblePriceTier` objects in MITx Online

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

## Importing users data
The way we match users from MicroMasters to MITxOnline is to use their social auth accounts they have explicitly linked from MicroMasters. 
If users don't have "mitxonline" social auth accounts on MicroMasters, then their data can't be imported

e.g. migrate user's enrollment data from MicroMasters to MITxOnline
```sql
SELECT
  
FROM micromasters.dashboard_cachedenrollment AS mm_enrollment
JOIN micromasters.social_auth_usersocialauth AS mm_social
  ON mm_enrollment.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
  ON mm_social.uid = mo_user.username
WHERE mm_social.provider = 'mitxonline'
```

## Testing

### Local setup
To run the import migration script locally, it needs a local foreign data connection named 'micromasters' mounted to
MicroMaster RC or production database

```
CREATE EXTENSION IF NOT EXISTS postgres_fdw;

CREATE SERVER IF NOT EXISTS micromaster_bridge
   FOREIGN DATA WRAPPER postgres_fdw
   OPTIONS (host 'xxxxx', dbname 'micromasters', port '15432');

CREATE USER MAPPING IF NOT EXISTS FOR postgres
   SERVER micromaster_bridge
   OPTIONS (user 'xxxxx', password 'xxxxx');

CREATE SCHEMA micromasters IF NOT EXISTS;
IMPORT FOREIGN SCHEMA public 
FROM SERVER micromaster_bridge INTO micromasters;

```
Note that the options values can be found by running the following command:
```
heroku config:get DATABASE_URL -a micromasters-rc
```
The output of the above command will look like:
```
postgres://<user>:<password>@<host>:<port>/<dbname>
```
Replace `host`, `dbname`, `port`, `user` and `password` values in foreign data wrapper queries with the values received from Heroku

### Running
Once foreign data wrapper is setup locally, then run the migration script like this:
```
docker-compose run --rm web ./manage.py import_micromasters_data --num 009
```
The above command will run the query /micromasters_import/management/commands/queries/009_import_course_certificate.sql
