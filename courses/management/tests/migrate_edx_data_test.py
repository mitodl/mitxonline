"""Tests for the migrate_edx_data management command"""

import ssl
from datetime import UTC, datetime
from io import StringIO

import pymysql
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from cms.factories import (
    CourseIndexPageFactory,
    CoursePageFactory,
    ProgramPageFactory,
    SignatoryPageFactory,
)
from cms.models import CourseIndexPage
from courses.factories import (
    CourseFactory,
    CourseRunCertificateFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    CourseRunGradeFactory,
    ProgramCertificateFactory,
)
from courses.management.commands import migrate_edx_data
from courses.management.commands.migrate_edx_data import (
    MIGRATION_SCHEMA,
    WAREHOUSE_STARROCKS,
    WAREHOUSE_TRINO,
    Command,
    _warehouse_list,
)
from courses.models import (
    Course,
    CourseRun,
    CourseRunCertificate,
    CourseRunEnrollment,
    CourseRunGrade,
    CourseRunGradeAudit,
    ProgramCertificate,
    ProgramEnrollment,
)
from users.factories import UserFactory
from users.models import LegalAddress, User, UserProfile

pytestmark = pytest.mark.django_db


class FakeCursor:
    """Minimal stand-in for a Trino or pymysql DB-API cursor."""

    def __init__(self, columns, rows, executed):
        self.description = [(col,) for col in columns]
        self._rows = rows
        self._offset = 0
        self._executed = executed

    def execute(self, query, args=None):
        """Record the query - the fake cursor already has its rows in memory."""
        self._executed.append((query, args))

    def fetchmany(self, size):
        """Return the next slice of rows, matching the DB-API contract."""
        batch = self._rows[self._offset : self._offset + size]
        self._offset += size
        return batch


class FakeConnection:
    """Minimal stand-in for a Trino or pymysql DB-API connection."""

    def __init__(self, columns, rows):
        self._columns = columns
        self._rows = rows
        self.executed = []

    def cursor(self):
        """Return a fresh fake cursor over the same fixed rows."""
        return FakeCursor(self._columns, self._rows, self.executed)


@pytest.fixture
def trino_settings(settings):
    """Read the migration tables from Trino"""
    settings.EDX_MIGRATION_WAREHOUSE = WAREHOUSE_TRINO
    settings.TRINO_HOST = "trino.example.com"
    settings.TRINO_PORT = 443
    settings.TRINO_USER = "reader"
    settings.TRINO_PASSWORD = "secret"  # noqa: S105
    settings.TRINO_CATALOG = "ol_data_lake_production"
    return settings


@pytest.fixture
def starrocks_settings(settings):
    """Read the migration tables from StarRocks"""
    settings.EDX_MIGRATION_WAREHOUSE = WAREHOUSE_STARROCKS
    settings.STARROCKS_HOST = "starrocks.example.com"
    settings.STARROCKS_USER = "reader"
    return settings


def test_connect_rejects_unknown_warehouse(settings, mocker):
    """An EDX_MIGRATION_WAREHOUSE other than trino or starrocks is an error"""
    settings.EDX_MIGRATION_WAREHOUSE = "galaxy"
    trino_connect = mocker.patch.object(migrate_edx_data.trino.dbapi, "connect")
    starrocks_connect = mocker.patch.object(migrate_edx_data.pymysql, "connect")

    with pytest.raises(CommandError, match="galaxy"):
        Command()._connect_to_warehouse()  # noqa: SLF001

    trino_connect.assert_not_called()
    starrocks_connect.assert_not_called()


@pytest.mark.parametrize("setting", ["TRINO_HOST", "TRINO_USER", "TRINO_CATALOG"])
def test_connect_requires_trino_settings(trino_settings, mocker, setting):
    """The command refuses to connect to Trino without a host, user and catalog"""
    setattr(trino_settings, setting, None)
    connect = mocker.patch.object(migrate_edx_data.trino.dbapi, "connect")

    with pytest.raises(CommandError, match=setting):
        Command()._connect_to_warehouse()  # noqa: SLF001

    connect.assert_not_called()


def test_connect_uses_trino_settings(trino_settings, mocker):
    """With EDX_MIGRATION_WAREHOUSE=trino the connection is opened from the TRINO_* settings"""
    trino_connect = mocker.patch.object(migrate_edx_data.trino.dbapi, "connect")
    starrocks_connect = mocker.patch.object(migrate_edx_data.pymysql, "connect")

    assert Command()._connect_to_warehouse() == trino_connect.return_value  # noqa: SLF001

    trino_connect.assert_called_once_with(
        host="trino.example.com",
        port=443,
        user="reader",
        auth=mocker.ANY,
        catalog="ol_data_lake_production",
        schema=MIGRATION_SCHEMA,
    )
    starrocks_connect.assert_not_called()


@pytest.mark.parametrize("setting", ["STARROCKS_HOST", "STARROCKS_USER"])
def test_connect_requires_starrocks_settings(starrocks_settings, mocker, setting):
    """The command refuses to connect to StarRocks without a host and user"""
    setattr(starrocks_settings, setting, None)
    connect = mocker.patch.object(migrate_edx_data.pymysql, "connect")

    with pytest.raises(CommandError, match=setting):
        Command()._connect_to_warehouse()  # noqa: SLF001

    connect.assert_not_called()


def test_connect_uses_starrocks_settings(settings, mocker):
    """With EDX_MIGRATION_WAREHOUSE=starrocks the connection is opened from the
    STARROCKS_* settings
    """
    settings.EDX_MIGRATION_WAREHOUSE = WAREHOUSE_STARROCKS
    settings.STARROCKS_HOST = "starrocks.example.com"
    settings.STARROCKS_PORT = 9030
    settings.STARROCKS_USER = "reader"
    settings.STARROCKS_PASSWORD = "secret"  # noqa: S105
    trino_connect = mocker.patch.object(migrate_edx_data.trino.dbapi, "connect")
    connect = mocker.patch.object(migrate_edx_data.pymysql, "connect")

    assert Command()._connect_to_warehouse() == connect.return_value  # noqa: SLF001

    connect.assert_called_once_with(
        host="starrocks.example.com",
        port=9030,
        user="reader",
        password="secret",  # noqa: S106
        ssl=mocker.ANY,
        cursorclass=pymysql.cursors.SSCursor,
        init_command="SET time_zone = '+00:00', query_timeout = 86400",
    )
    trino_connect.assert_not_called()


@pytest.mark.usefixtures("starrocks_settings")
def test_connect_verifies_certificate_and_hostname(mocker):
    """The TLS context pymysql builds from the command's arguments checks both
    the chain and the hostname
    """
    connect = mocker.patch.object(migrate_edx_data.pymysql, "connect")

    Command()._connect_to_warehouse()  # noqa: SLF001

    conn = pymysql.connections.Connection(
        **connect.call_args.kwargs, defer_connect=True
    )
    assert conn.ctx.verify_mode == ssl.CERT_REQUIRED
    assert conn.ctx.check_hostname is True


@pytest.mark.parametrize(
    ("warehouse_settings", "placeholders"),
    [("trino_settings", "?, ?"), ("starrocks_settings", "%s, %s")],
)
def test_course_certificates_query_binds_readable_ids(
    request, warehouse_settings, placeholders
):
    """Course run readable ids are bound as parameters in the driver's paramstyle,
    and the table is qualified with its catalog and schema
    """
    request.getfixturevalue(warehouse_settings)
    conn = FakeConnection(columns=[], rows=[])

    Command()._migrate_course_certificates(  # noqa: SLF001
        conn,
        {"courserun_readable_ids": "course-v1:MITx+1+1T2024, course-v1:MITx+2'x"},
    )

    [(query, args)] = conn.executed
    assert (
        f"FROM ol_data_lake_production.{MIGRATION_SCHEMA}.edxorg_to_mitxonline_enrollments "
        in query
    )
    assert f"courserun_readable_id IN ({placeholders})" in query
    assert args == ["course-v1:MITx+1+1T2024", "course-v1:MITx+2'x"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('["Jane Doe", "John Roe"]', ["Jane Doe", "John Roe"]),
        (b'["Jane Doe"]', ["Jane Doe"]),
        (["Jane Doe"], ["Jane Doe"]),
        (None, []),
    ],
)
def test_warehouse_list(value, expected):
    """An array column arrives from StarRocks as JSON text"""
    assert _warehouse_list(value) == expected


def test_get_signatories_reads_the_array_column():
    """signatory_names arrives as JSON text, and matches signatories by name"""
    signatory, _ = SignatoryPageFactory.create_batch(2)

    signatories = Command()._get_signatories(  # noqa: SLF001
        f'["{signatory.name}", " "]', use_default_signatory=False
    )

    assert signatories == [signatory]


def test_create_course_run_reads_warehouse_types():
    """StarRocks sends timestamps naive, in the session's UTC, and booleans as 0 or 1"""
    course = CourseFactory.create()
    row = {
        "courseware_id": "course-v1:MITx+1.00x+1T2024",
        "run_tag": "1T2024",
        "start_date": datetime(2024, 1, 2, 15, 0),  # noqa: DTZ001
        "end_date": datetime(2024, 5, 1, 15, 0),  # noqa: DTZ001
        "enrollment_start": datetime(2023, 12, 1, 15, 0),  # noqa: DTZ001
        "enrollment_end": None,
        "courserun_title": "Run",
        "is_self_paced": 1,
    }

    run, created = Command()._create_course_run(course, row)  # noqa: SLF001

    assert created
    run.refresh_from_db()
    assert run.start_date == datetime(2024, 1, 2, 15, 0, tzinfo=UTC)
    assert run.end_date == datetime(2024, 5, 1, 15, 0, tzinfo=UTC)
    assert run.enrollment_start == datetime(2023, 12, 1, 15, 0, tzinfo=UTC)
    assert run.enrollment_end is None
    assert run.is_self_paced is True


USER_COLUMNS = [
    "user_email",
    "user_full_name",
    "user_address_country",
    "user_address_state",
    "user_address_postal_code",
    "user_address_street_1",
    "user_address_street_2",
    "user_address_city",
    "user_gender",
    "user_birth_year",
]


def _user_row(email, name, country="US"):
    return (
        email,
        name,
        country,
        "MA",
        "02139",
        "1 Main St",
        "",
        "Cambridge",
        None,
        None,
    )


def _break_user(user):
    """Simulate the historical bug's effect: a User row with no
    LegalAddress or UserProfile at all.
    """
    LegalAddress.objects.filter(user=user).delete()
    UserProfile.objects.filter(user=user).delete()


def test_bulk_create_users_returns_real_ids():
    """_bulk_create_users must return objects with real, populated ids -
    bulk_create(ignore_conflicts=True) never sets .pk on its own, on any
    backend, so this only works if the returned rows are re-fetched
    """
    rows = [{"user_email": "new@example.com", "user_full_name": "New User"}]

    created = Command._bulk_create_users(  # noqa: SLF001
        rows, existing_emails=set(), batch_size=100
    )

    assert len(created) == 1
    assert created[0].id is not None
    assert User.objects.get(email="new@example.com").id == created[0].id


def test_migrate_users_creates_legal_address_and_profile():
    """End to end through _migrate_users: new users must actually get
    LegalAddress and UserProfile rows, not just a User row
    """
    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row("alice@example.com", "Alice A", country="US")],
    )

    Command()._migrate_users(conn, {})  # noqa: SLF001

    user = User.objects.get(email="alice@example.com")
    assert user.legal_address.country == "US"
    assert UserProfile.objects.filter(user=user).exists()


def test_migrate_users_multiple_new_users_in_one_batch():
    """Multiple new users in a single batch must each get their own
    LegalAddress - previously, every user.id was None, so id_row_lookup
    collapsed every entry onto the same None key and only one user's row
    data survived
    """
    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[
            _user_row("alice@example.com", "Alice A", country="US"),
            _user_row("bob@example.com", "Bob B", country="CA"),
        ],
    )

    Command()._migrate_users(conn, {})  # noqa: SLF001

    alice = User.objects.get(email="alice@example.com")
    bob = User.objects.get(email="bob@example.com")
    assert alice.legal_address.country == "US"
    assert bob.legal_address.country == "CA"
    assert UserProfile.objects.filter(user=alice).exists()
    assert UserProfile.objects.filter(user=bob).exists()


def test_migrate_users_skips_existing_emails():
    """A user who already exists in mitxonline must not get a duplicate
    User row, and their existing LegalAddress/UserProfile must be left
    alone
    """
    existing_user = UserFactory.create(email="existing@example.com")
    LegalAddress.objects.filter(user=existing_user).delete()

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(existing_user.email, "Existing User", country="US")],
    )

    Command()._migrate_users(conn, {})  # noqa: SLF001

    assert User.objects.filter(email=existing_user.email).count() == 1
    assert not LegalAddress.objects.filter(user=existing_user).exists()


def test_repair_creates_missing_legal_address_and_profile():
    """A user missing both rows gets both created from the matching edX row"""
    user = UserFactory.create(email="broken@example.com")
    _break_user(user)

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Broken User", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    user.refresh_from_db()
    assert user.legal_address.country == "US"
    assert UserProfile.objects.filter(user=user).exists()


def test_repair_only_backfills_missing_piece():
    """A user missing only UserProfile (LegalAddress already exists) only
    gets UserProfile created - the existing helpers must not touch or
    duplicate the LegalAddress that's already there
    """
    user = UserFactory.create(email="half-broken@example.com")
    user.legal_address.country = "CA"
    user.legal_address.save()
    UserProfile.objects.filter(user=user).delete()

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Half Broken", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    user.refresh_from_db()
    assert user.legal_address.country == "CA"
    assert UserProfile.objects.filter(user=user).exists()


def test_repair_skips_users_with_no_missing_rows():
    """A user who already has both rows is left untouched, even though a
    matching edX row exists for their email
    """
    user = UserFactory.create(email="fine@example.com")
    user.legal_address.country = "MX"
    user.legal_address.save()

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Fine User", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    user.refresh_from_db()
    assert user.legal_address.country == "MX"


def test_repair_leaves_unmatched_user_broken_without_crashing():
    """An affected user with no corresponding row in edxorg_to_mitxonline_users
    (e.g. their edX data was never in that table) is reported as still
    missing, not silently invented from nothing
    """
    user = UserFactory.create(email="no-edx-row@example.com")
    _break_user(user)

    conn = FakeConnection(columns=USER_COLUMNS, rows=[])

    Command()._repair_migrated_user_profiles(conn, {})  # noqa: SLF001

    assert not LegalAddress.objects.filter(user=user).exists()
    assert not UserProfile.objects.filter(user=user).exists()


def test_dry_run_does_not_write():
    """--dry-run must not create any rows, even for a clearly matched user"""
    user = UserFactory.create(email="dry-run@example.com")
    _break_user(user)

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Dry Run User", country="US")],
    )

    Command()._repair_migrated_user_profiles(conn, {"dry_run": True})  # noqa: SLF001

    assert not LegalAddress.objects.filter(user=user).exists()
    assert not UserProfile.objects.filter(user=user).exists()


def test_limit_caps_number_of_users_repaired():
    """--limit caps how many affected users are considered at all, leaving
    the rest broken for a later run
    """
    users = [UserFactory.create(email=f"limited-{i}@example.com") for i in range(3)]
    for user in users:
        _break_user(user)

    conn = FakeConnection(
        columns=USER_COLUMNS,
        rows=[_user_row(user.email, "Limited User", country="US") for user in users],
    )

    Command()._repair_migrated_user_profiles(conn, {"limit": 1})  # noqa: SLF001

    repaired = User.objects.filter(legal_address__isnull=False).count()
    assert repaired == 1


def test_migrate_users_dry_run_creates_no_records(capsys):
    """--dry-run must not create any User/LegalAddress/UserProfile rows"""
    existing_user = UserFactory.create(email="existing@example.com")
    conn = FakeConnection(
        columns=["user_email", "user_full_name"],
        rows=[
            ("new1@example.com", "New One"),
            ("new2@example.com", "New Two"),
            (existing_user.email, "Existing User"),
        ],
    )

    Command()._migrate_users(conn, {"dry_run": True})  # noqa: SLF001

    assert User.objects.count() == 1  # only the pre-existing user
    output = capsys.readouterr().out
    assert "[DRY RUN] Would create 2 users" in output


def test_migrate_users_dry_run_respects_batching(capsys):
    """The dry-run count must accumulate correctly across multiple fetchmany
    batches, not just within a single batch
    """
    conn = FakeConnection(
        columns=["user_email", "user_full_name"],
        rows=[(f"new{i}@example.com", f"New {i}") for i in range(5)],
    )

    Command()._migrate_users(conn, {"dry_run": True, "batch_size": 2})  # noqa: SLF001

    assert User.objects.count() == 0
    output = capsys.readouterr().out
    assert "[DRY RUN] Would create 5 users" in output


def test_migrate_users_dry_run_excludes_existing_usernames(capsys):
    """An incoming email that matches an existing user's username (but not
    their email) would conflict on create, so dry-run must not count it
    """
    UserFactory.create(username="taken@example.com", email="other@example.com")
    conn = FakeConnection(
        columns=["user_email", "user_full_name"],
        rows=[("taken@example.com", "Taken"), ("new@example.com", "New")],
    )

    Command()._migrate_users(conn, {"dry_run": True})  # noqa: SLF001

    assert "[DRY RUN] Would create 1 users" in capsys.readouterr().out


def test_migrate_users_dry_run_matches_emails_case_insensitively(capsys):
    """Email uniqueness ignores case, so dry-run must not count an email that
    differs from an existing user's only by case, or count two case variants
    of one new email twice - including across batches
    """
    UserFactory.create(email="Existing@example.com")
    conn = FakeConnection(
        columns=["user_email", "user_full_name"],
        rows=[
            ("existing@example.com", "Existing"),
            ("New@example.com", "New"),
            ("new@example.com", "New Again"),
        ],
    )

    Command()._migrate_users(conn, {"dry_run": True, "batch_size": 2})  # noqa: SLF001

    assert "[DRY RUN] Would create 1 users" in capsys.readouterr().out


@pytest.mark.parametrize("letter_grade", ["A", None])
def test_bulk_create_grades_sets_letter_grade(letter_grade):
    """Migrated certificate grades get the edX.org letter grade"""
    user = UserFactory.create()
    run = CourseRunFactory.create()

    Command._bulk_create_grades(  # noqa: SLF001
        [
            {
                "user_mitxonline_id": user.id,
                "courserun_id": run.id,
                "courserungrade_grade": 0.9,
                "courserungrade_is_passing": True,
                "courserungrade_letter_grade": letter_grade,
            }
        ],
        batch_size=10,
    )

    assert (
        CourseRunGrade.objects.get(user=user, course_run=run).letter_grade
        == letter_grade
    )


LETTER_GRADE_COLUMNS = [
    "user_mitxonline_id",
    "courserun_id",
    "courserungrade_letter_grade",
]


def _letter_grade_conn(rows):
    return FakeConnection(
        columns=LETTER_GRADE_COLUMNS,
        rows=[(grade.user_id, grade.course_run_id, letter) for grade, letter in rows],
    )


@pytest.mark.parametrize("blank_letter", [None, ""])
@pytest.mark.parametrize("set_by_admin", [True, False])
def test_backfill_letter_grades_fills_blank_grade(blank_letter, set_by_admin):
    """A grade with no letter grade gets the edX.org letter grade and an audit row,
    whether or not an admin set the grade
    """
    grade = CourseRunGradeFactory.create(
        letter_grade=blank_letter, set_by_admin=set_by_admin
    )

    Command()._backfill_letter_grades(_letter_grade_conn([(grade, "Pass")]), {})  # noqa: SLF001

    grade.refresh_from_db()
    assert grade.letter_grade == "Pass"
    audit = CourseRunGradeAudit.objects.get(course_run_grade=grade)
    assert audit.acting_user is None
    assert audit.data_before["letter_grade"] == blank_letter
    assert audit.data_after["letter_grade"] == "Pass"


@pytest.mark.parametrize(
    ("letter_grade", "set_by_admin"),
    [("B", False), ("A", True)],
)
def test_backfill_letter_grades_keeps_existing_letter_grade(letter_grade, set_by_admin):
    """Grades that already have a letter grade are not changed"""
    grade = CourseRunGradeFactory.create(
        letter_grade=letter_grade, set_by_admin=set_by_admin
    )

    Command()._backfill_letter_grades(_letter_grade_conn([(grade, "Pass")]), {})  # noqa: SLF001

    grade.refresh_from_db()
    assert grade.letter_grade == letter_grade
    assert not CourseRunGradeAudit.objects.filter(course_run_grade=grade).exists()


def test_backfill_letter_grades_matches_user_and_run_pairs():
    """A grade matches only on its own user and run pair, even when its user and its
    run each appear in other rows of the same batch
    """
    run_a, run_b = CourseRunFactory.create_batch(2)
    user_a, user_b = UserFactory.create_batch(2)
    grade_a = CourseRunGradeFactory.create(
        user=user_a, course_run=run_a, letter_grade=None, set_by_admin=False
    )
    grade_b = CourseRunGradeFactory.create(
        user=user_b, course_run=run_b, letter_grade=None, set_by_admin=False
    )
    unmatched = CourseRunGradeFactory.create(
        user=user_a, course_run=run_b, letter_grade=None, set_by_admin=False
    )

    Command()._backfill_letter_grades(  # noqa: SLF001
        _letter_grade_conn([(grade_a, "A"), (grade_b, "C")]), {"batch_size": 10}
    )

    for grade in (grade_a, grade_b, unmatched):
        grade.refresh_from_db()
    assert grade_a.letter_grade == "A"
    assert grade_b.letter_grade == "C"
    assert unmatched.letter_grade is None


def test_backfill_letter_grades_dry_run_does_not_write():
    """--dry-run counts the grades it would update but does not change them"""
    grade = CourseRunGradeFactory.create(letter_grade=None, set_by_admin=False)
    stdout = StringIO()

    Command(stdout=stdout)._backfill_letter_grades(  # noqa: SLF001
        _letter_grade_conn([(grade, "A")]), {"dry_run": True}
    )

    assert "Would update 1 letter grades" in stdout.getvalue()
    grade.refresh_from_db()
    assert grade.letter_grade is None
    assert not CourseRunGradeAudit.objects.filter(course_run_grade=grade).exists()


@pytest.mark.usefixtures("starrocks_settings")
@pytest.mark.parametrize(
    ("options", "expected_clause", "expected_params"),
    [
        ({}, None, []),
        (
            {
                "courserun_readable_ids": "course-v1:MITx+A+1T2020, course-v1:MITx+B+1T2020"
            },
            " WHERE courserun_readable_id IN (%s, %s)",
            ["course-v1:MITx+A+1T2020", "course-v1:MITx+B+1T2020"],
        ),
        (
            {"courserun_readable_ids": "course-v1:MITx+A+1T2020' OR '1'='1"},
            " WHERE courserun_readable_id IN (%s)",
            ["course-v1:MITx+A+1T2020' OR '1'='1"],
        ),
    ],
)
def test_backfill_letter_grades_binds_courserun_filter(
    options, expected_clause, expected_params
):
    """--courserun-readable-ids values are bound as parameters, not put in the SQL"""
    conn = FakeConnection(columns=LETTER_GRADE_COLUMNS, rows=[])

    Command(stdout=StringIO())._backfill_letter_grades(  # noqa: SLF001
        conn, {**options, "limit": 5}
    )

    [(query, params)] = conn.executed
    assert query.endswith(f"{expected_clause or ''} LIMIT 5")
    assert "'" not in query
    assert params == expected_params


@pytest.mark.usefixtures("starrocks_settings")
def test_migrate_course_certificates_binds_courserun_filter():
    """The course_certificates migration uses the same bound filter"""
    conn = FakeConnection(columns=["user_mitxonline_id"], rows=[])

    Command(stdout=StringIO())._migrate_course_certificates(  # noqa: SLF001
        conn, {"courserun_readable_ids": "course-v1:MITx+A+1T2020"}
    )

    [(query, params)] = conn.executed
    assert query.endswith(" AND courserun_readable_id IN (%s)")
    assert params == ["course-v1:MITx+A+1T2020"]


@pytest.mark.parametrize(
    ("helper", "model", "date_column", "id_column"),
    [
        (
            "_bulk_create_certificates",
            "CourseRunCertificate",
            "courseruncertificate_created_on",
            "courserun_id",
        ),
        (
            "_bulk_create_program_certificates",
            "ProgramCertificate",
            "program_certificate_issued_on",
            "program_id",
        ),
    ],
)
def test_bulk_create_certificates_reads_naive_issue_date_as_utc(
    mocker, helper, model, date_column, id_column
):
    """StarRocks sends certificate dates naive, in the session's UTC time zone"""
    bulk_create = mocker.patch.object(
        getattr(migrate_edx_data, model).objects, "bulk_create"
    )

    getattr(Command, helper)(
        [
            {
                "user_mitxonline_id": 1,
                id_column: 2,
                date_column: datetime(2024, 5, 6, 7, 8, 9),  # noqa: DTZ001
                "certificate_page_revision_id": None,
            }
        ],
        batch_size=10,
    )

    [certificate] = bulk_create.call_args.args[0]
    assert certificate.issue_date == datetime(2024, 5, 6, 7, 8, 9, tzinfo=UTC)


def test_handle_rejects_type_not_available_for_platform(mocker):
    """An edX.org-only type is an error for another platform, before connecting"""
    connect = mocker.patch.object(Command, "_connect_to_warehouse")

    with pytest.raises(CommandError, match="entitlements is not available"):
        call_command("migrate_edx_data", platform="xpro", type="entitlements")

    connect.assert_not_called()


@pytest.mark.parametrize(
    ("migrate_type", "method"),
    [
        ("course_runs", "_migrate_course_runs"),
        ("users", "_migrate_users"),
        ("course_enrollments", "_migrate_course_enrollments"),
        ("program_certificates", "_migrate_platform_program_certificates"),
    ],
)
def test_handle_runs_platform_migration(mocker, migrate_type, method):
    """--platform xpro runs the migration that reads the mitxonline_migration_* tables"""
    mocker.patch.object(Command, "_connect_to_warehouse")
    migrate = mocker.patch.object(Command, method)

    call_command(
        "migrate_edx_data", platform="xpro", type=migrate_type, stdout=StringIO()
    )

    migrate.assert_called_once()
    assert migrate.call_args.args[1]["platform"] == "xpro"


@pytest.mark.usefixtures("trino_settings")
def test_platform_users_read_the_platform_rows():
    """--platform xpro reads its own rows of mitxonline_migration_users"""
    conn = FakeConnection(
        columns=USER_COLUMNS, rows=[_user_row("xpro@example.com", "X Learner")]
    )

    Command(stdout=StringIO())._migrate_users(conn, {"platform": "xpro"})  # noqa: SLF001

    [(query, _)] = conn.executed
    assert query == (
        f"SELECT * FROM ol_data_lake_production.{MIGRATION_SCHEMA}."  # noqa: S608
        "mitxonline_migration_users WHERE source = 'xpro'"
    )
    user = User.objects.get(email="xpro@example.com")
    assert user.legal_address.country == "US"


PLATFORM_COURSE_RUN_COLUMNS = [
    "source",
    "mitxonline_course_id",
    "course_readable_id",
    "course_title",
    "courserun_title",
    "courseware_id",
    "run_tag",
    "enrollment_start",
    "enrollment_end",
    "start_date",
    "end_date",
    "is_self_paced",
    "is_published",
]


@pytest.mark.parametrize("is_published", [True, False])
def test_platform_course_runs_create_course_without_department(is_published):
    """The platform tables have no department or signatory names; the course,
    its pages and the run are still created
    """
    if not CourseIndexPage.objects.filter(live=True).exists():
        CourseIndexPageFactory.create()
    conn = FakeConnection(
        columns=PLATFORM_COURSE_RUN_COLUMNS,
        rows=[
            (
                "xpro",
                None,
                "course-v1:xPRO+PCC",
                "Course",
                "Run",
                "course-v1:xPRO+PCC+R1",
                "R1",
                None,
                datetime(2024, 1, 1, tzinfo=UTC),
                datetime(2024, 1, 2, tzinfo=UTC),
                datetime(2024, 5, 1, tzinfo=UTC),
                False,
                is_published,
            )
        ],
    )

    Command(stdout=StringIO())._migrate_course_runs(  # noqa: SLF001
        conn, {"platform": "xpro", "use_default_signatory": False}
    )

    course = Course.objects.get(readable_id="course-v1:xPRO+PCC")
    assert not course.departments.exists()
    assert course.get_certificate_page_revision() is not None
    run = CourseRun.objects.get(courseware_id="course-v1:xPRO+PCC+R1")
    assert run.course == course
    assert run.live is is_published


ENROLLMENT_COLUMNS = [
    "source",
    "migration_status",
    "user_mitxonline_id",
    "courserun_id",
    "courserunenrollment_enrollment_mode",
    "courserunenrollment_is_active",
    "courserungrade_grade",
    "courserungrade_letter_grade",
    "courserungrade_is_passing",
    "courseruncertificate_uuid",
    "courseruncertificate_is_revoked",
    "courseruncertificate_created_on",
]
CERTIFICATE_UUID = "6f1c1a3e-2a8e-4d55-9a57-0b6c1f0a9d11"


@pytest.fixture
def course_run():
    """A course run whose course has a certificate page"""
    return CourseRunFactory.create(course=CoursePageFactory.create().course)


def _enrollment_row(  # noqa: PLR0913
    status,
    user,
    run,
    *,
    is_active=True,
    grade=0.9,
    is_revoked=False,
    issued_on="2024-05-06T07:08:09Z",
):
    return (
        "xpro",
        status,
        user.id,
        run.id,
        "verified",
        is_active,
        grade,
        "A" if grade is not None else None,
        grade is not None,
        CERTIFICATE_UUID if issued_on else None,
        is_revoked if issued_on else None,
        issued_on,
    )


def _migrate_course_enrollments(rows, **options):
    conn = FakeConnection(columns=ENROLLMENT_COLUMNS, rows=rows)
    Command(stdout=StringIO())._migrate_course_enrollments(  # noqa: SLF001
        conn, {"platform": "xpro", **options}
    )
    return conn


@pytest.mark.usefixtures("trino_settings")
def test_course_enrollments_query_filters_platform_and_runs():
    """The query reads the platform's rows that have MITx Online ids, with the
    course run filter bound as a parameter
    """
    conn = _migrate_course_enrollments([], courserun_readable_ids="course-v1:xPRO+A+R1")

    [(query, params)] = conn.executed
    assert query == (
        f"SELECT * FROM ol_data_lake_production.{MIGRATION_SCHEMA}."  # noqa: S608
        "mitxonline_migration_course_enrollments WHERE source = 'xpro' "
        "AND user_mitxonline_id IS NOT NULL AND courserun_id IS NOT NULL "
        "AND courserun_readable_id IN (?)"
    )
    assert params == ["course-v1:xPRO+A+R1"]


def test_course_enrollments_new_row_creates_enrollment_grade_and_certificate(
    course_run,
):
    """A new row creates the enrollment, the grade and the certificate, which
    keeps the source's UUID and issue date
    """
    user = UserFactory.create()

    _migrate_course_enrollments([_enrollment_row("new", user, course_run)])

    enrollment = CourseRunEnrollment.objects.get(user=user, run=course_run)
    assert enrollment.enrollment_mode == "verified"
    assert enrollment.edx_enrolled is True
    grade = CourseRunGrade.objects.get(user=user, course_run=course_run)
    assert (grade.grade, grade.letter_grade, grade.passed) == (0.9, "A", True)
    certificate = CourseRunCertificate.objects.get(user=user, course_run=course_run)
    assert str(certificate.uuid) == CERTIFICATE_UUID
    assert certificate.issue_date == datetime(2024, 5, 6, 7, 8, 9, tzinfo=UTC)
    assert certificate.certificate_page_revision is not None


@pytest.mark.parametrize("is_active", [True, False])
def test_course_enrollments_status_changed_sets_active(course_run, is_active):
    """A status_changed row sets the enrollment's active status"""
    enrollment = CourseRunEnrollmentFactory.create(run=course_run, active=not is_active)

    _migrate_course_enrollments(
        [
            _enrollment_row(
                "status_changed", enrollment.user, course_run, is_active=is_active
            )
        ]
    )

    enrollment.refresh_from_db()
    assert enrollment.active is is_active


def test_course_enrollments_grade_changed_updates_grade_with_audit(course_run):
    """A grade_changed row updates the grade and writes an audit row"""
    grade = CourseRunGradeFactory.create(
        course_run=course_run,
        grade=0.2,
        passed=False,
        letter_grade="F",
        set_by_admin=False,
    )

    _migrate_course_enrollments(
        [_enrollment_row("grade_changed", grade.user, course_run, issued_on=None)]
    )

    grade.refresh_from_db()
    assert (grade.grade, grade.letter_grade, grade.passed) == (0.9, "A", True)
    audit = CourseRunGradeAudit.objects.get(course_run_grade=grade)
    assert audit.data_before["grade"] == 0.2
    assert audit.data_after["grade"] == 0.9


@pytest.mark.parametrize("is_revoked", [True, False])
def test_course_enrollments_certificate_changed_sets_revoked(course_run, is_revoked):
    """A certificate_changed row sets the existing certificate's revoked status"""
    certificate = CourseRunCertificateFactory.create(
        course_run=course_run, is_revoked=not is_revoked
    )

    _migrate_course_enrollments(
        [
            _enrollment_row(
                "certificate_changed",
                certificate.user,
                course_run,
                is_revoked=is_revoked,
            )
        ]
    )

    certificate.refresh_from_db()
    assert certificate.is_revoked is is_revoked
    assert CourseRunCertificate.all_objects.filter(user=certificate.user).count() == 1


def test_course_enrollments_dry_run_does_not_write(course_run):
    """A dry run counts the changes and writes nothing"""
    new_user = UserFactory.create()
    enrollment = CourseRunEnrollmentFactory.create(run=course_run, active=True)
    grade = CourseRunGradeFactory.create(
        course_run=course_run, grade=0.2, set_by_admin=False
    )
    stdout = StringIO()
    conn = FakeConnection(
        columns=ENROLLMENT_COLUMNS,
        rows=[
            _enrollment_row("new", new_user, course_run),
            _enrollment_row(
                "status_changed", enrollment.user, course_run, is_active=False
            ),
            _enrollment_row("grade_changed", grade.user, course_run, issued_on=None),
        ],
    )

    Command(stdout=stdout)._migrate_course_enrollments(  # noqa: SLF001
        conn, {"platform": "xpro", "dry_run": True}
    )

    assert not CourseRunEnrollment.all_objects.filter(user=new_user).exists()
    assert not CourseRunCertificate.all_objects.exists()
    enrollment.refresh_from_db()
    grade.refresh_from_db()
    assert enrollment.active is True
    assert grade.grade == 0.2
    assert (
        "[DRY RUN] Would write: 1 enrollments created, 1 enrollments updated, "
        "1 grades created, 1 grades updated, 1 certificates created, "
        "0 certificates updated"
    ) in stdout.getvalue()


PROGRAM_CERTIFICATE_COLUMNS = [
    "source",
    "migration_status",
    "user_mitxonline_id",
    "program_id",
    "programcertificate_uuid",
    "programcertificate_is_revoked",
    "program_certificate_issued_on",
]


def _migrate_program_certificates(rows):
    conn = FakeConnection(columns=PROGRAM_CERTIFICATE_COLUMNS, rows=rows)
    Command(stdout=StringIO())._migrate_platform_program_certificates(  # noqa: SLF001
        conn, {"platform": "xpro"}
    )
    return conn


@pytest.mark.usefixtures("trino_settings")
def test_platform_program_certificates_new_row_creates_enrollment_and_certificate():
    """A new row creates the program enrollment and the certificate"""
    program = ProgramPageFactory.create().program
    user = UserFactory.create()

    conn = _migrate_program_certificates(
        [
            (
                "xpro",
                "new",
                user.id,
                program.id,
                CERTIFICATE_UUID,
                False,
                "2024-05-06T07:08:09Z",
            )
        ]
    )

    [(query, _)] = conn.executed
    assert query.endswith(
        "mitxonline_migration_program_certificates WHERE source = 'xpro' "
        "AND user_mitxonline_id IS NOT NULL AND program_id IS NOT NULL"
    )
    assert ProgramEnrollment.objects.filter(user=user, program=program).exists()
    certificate = ProgramCertificate.objects.get(user=user, program=program)
    assert str(certificate.uuid) == CERTIFICATE_UUID
    assert certificate.issue_date == datetime(2024, 5, 6, 7, 8, 9, tzinfo=UTC)


def test_platform_program_certificates_certificate_changed_revokes():
    """A certificate_changed row sets the existing certificate's revoked status"""
    certificate = ProgramCertificateFactory.create(
        program=ProgramPageFactory.create().program
    )

    _migrate_program_certificates(
        [
            (
                "xpro",
                "certificate_changed",
                certificate.user_id,
                certificate.program_id,
                CERTIFICATE_UUID,
                True,
                "2024-05-06T07:08:09Z",
            )
        ]
    )

    certificate.refresh_from_db()
    assert certificate.is_revoked is True
    assert not ProgramEnrollment.all_objects.filter(user=certificate.user).exists()


@pytest.mark.parametrize(
    ("migrate_type", "method"),
    [
        ("course_runs", "_migrate_course_runs"),
        ("program_certificates", "_migrate_program_certificates"),
        ("letter_grades", "_backfill_letter_grades"),
    ],
)
def test_handle_defaults_to_edxorg(mocker, migrate_type, method):
    """Without --platform the command runs the edX.org migrations, as before"""
    mocker.patch.object(Command, "_connect_to_warehouse")
    migrate = mocker.patch.object(Command, method)

    call_command("migrate_edx_data", type=migrate_type, stdout=StringIO())

    migrate.assert_called_once()
    assert migrate.call_args.args[1]["platform"] == "edxorg"


EDXORG_COURSE_RUN_COLUMNS = [
    *PLATFORM_COURSE_RUN_COLUMNS,
    "department_name",
    "signatory_names",
    "certificate_count",
]


@pytest.mark.usefixtures("trino_settings")
def test_edxorg_course_runs_stay_live_with_department():
    """edX.org runs are live even when edX.org has them unpublished, and the
    course gets its department
    """
    if not CourseIndexPage.objects.filter(live=True).exists():
        CourseIndexPageFactory.create()
    signatory = SignatoryPageFactory.create()
    conn = FakeConnection(
        columns=EDXORG_COURSE_RUN_COLUMNS,
        rows=[
            (
                "edxorg",
                None,
                "course-v1:MITx+6.00x",
                "Course",
                "Run",
                "course-v1:MITx+6.00x+1T2024",
                "1T2024",
                None,
                None,
                None,
                None,
                False,
                False,
                "Electrical Engineering",
                f'["{signatory.name}"]',
                3,
            )
        ],
    )

    Command(stdout=StringIO())._migrate_course_runs(  # noqa: SLF001
        conn, {"use_default_signatory": False}
    )

    [(query, _)] = conn.executed
    assert query == (
        f"SELECT * FROM ol_data_lake_production.{MIGRATION_SCHEMA}."  # noqa: S608
        "edxorg_to_mitxonline_course_runs"
    )
    course = Course.objects.get(readable_id="course-v1:MITx+6.00x")
    assert list(course.departments.values_list("name", flat=True)) == [
        "Electrical Engineering"
    ]
    assert CourseRun.objects.get(courseware_id="course-v1:MITx+6.00x+1T2024").live
