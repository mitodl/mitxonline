"""Tests for migrate_edx_data management command's user migration
(bulk_create fix and --dry-run), repair_migrated_profiles type and letter_grades type
"""

from io import StringIO

import pytest

from courses.factories import CourseRunFactory, CourseRunGradeFactory
from courses.management.commands.migrate_edx_data import Command
from courses.models import CourseRunGradeAudit
from users.factories import UserFactory
from users.models import LegalAddress, User, UserProfile

pytestmark = pytest.mark.django_db


class FakeCursor:
    """Minimal stand-in for a Trino DB-API cursor."""

    def __init__(self, columns, rows):
        self.description = [(col,) for col in columns]
        self._rows = rows
        self._offset = 0
        self.query = None
        self.params = None

    def execute(self, query, params=None):
        """Record the query - the fake cursor already has its rows in memory."""
        self.query = query
        self.params = params

    def fetchmany(self, size):
        """Return the next slice of rows, matching the DB-API contract."""
        batch = self._rows[self._offset : self._offset + size]
        self._offset += size
        return batch


class FakeConnection:
    """Minimal stand-in for a Trino DB-API connection."""

    def __init__(self, columns, rows):
        self._columns = columns
        self._rows = rows
        self.last_cursor = None

    def cursor(self):
        """Return a fresh fake cursor over the same fixed rows."""
        self.last_cursor = FakeCursor(self._columns, self._rows)
        return self.last_cursor


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


@pytest.mark.parametrize(
    ("options", "expected_clause", "expected_params"),
    [
        ({}, None, []),
        (
            {
                "courserun_readable_ids": "course-v1:MITx+A+1T2020, course-v1:MITx+B+1T2020"
            },
            " WHERE courserun_readable_id IN (?,?)",
            ["course-v1:MITx+A+1T2020", "course-v1:MITx+B+1T2020"],
        ),
        (
            {"courserun_readable_ids": "course-v1:MITx+A+1T2020' OR '1'='1"},
            " WHERE courserun_readable_id IN (?)",
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

    query = conn.last_cursor.query
    assert query.endswith(f"{expected_clause or ''} LIMIT 5")
    assert "'" not in query
    assert conn.last_cursor.params == expected_params


def test_migrate_course_certificates_binds_courserun_filter():
    """The course_certificates migration uses the same bound filter"""
    conn = FakeConnection(columns=["user_mitxonline_id"], rows=[])

    Command(stdout=StringIO())._migrate_course_certificates(  # noqa: SLF001
        conn, {"courserun_readable_ids": "course-v1:MITx+A+1T2020"}
    )

    assert conn.last_cursor.query.endswith(" AND courserun_readable_id IN (?)")
    assert conn.last_cursor.params == ["course-v1:MITx+A+1T2020"]
