"""Tests for B2B contract provisioning."""

from decimal import Decimal

import pytest

from b2b.api import ensure_enrollment_codes_exist
from b2b.constants import (
    CONTRACT_MEMBERSHIP_AUTO,
    CONTRACT_MEMBERSHIP_CODE,
    CONTRACT_MEMBERSHIP_MANAGED,
    PROVISIONING_ACTION_CONTRACT_VARIANT_ADDED,
    PROVISIONING_ACTION_CONTRACT_VARIANT_UPDATED,
)
from b2b.contracts import (
    add_contract_variant_set,
    add_courseware_to_contract,
    create_contract,
    ensure_default_variant,
    expected_enrollment_code_count,
    expire_unused_enrollment_codes,
    get_contract_variant_coverage,
    remove_courseware_from_contract,
    sync_contract_variants,
    update_contract_variant_set,
)
from b2b.exceptions import ContractVariantError, SourceCourseIncompleteError
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import (
    DiscountContractAttachmentRedemption,
    OrganizationProvisioningAudit,
)
from courses.factories import (
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    ProgramFactory,
)
from users.factories import UserFactory
from variants.factories import CourseSupportedVariantFactory

pytestmark = [pytest.mark.django_db]


@pytest.fixture(autouse=True)
def mocked_edx(mocker):
    """Keep contract run creation and removal away from edX."""

    mocker.patch("b2b.contracts.push_run_dates_to_edx")
    return mocker.patch("openedx.tasks.clone_courserun.delay")


def _source_run():
    """Create a course with a source run contract runs can be cloned from."""

    return CourseRunFactory.create(
        is_source_run=True, language="en", is_primary_language=True
    )


def test_create_contract():
    """A new contract sits under its organization with a default variant set."""

    organization = OrganizationPageFactory.create()

    contract = create_contract(
        organization,
        name="Spring cohort",
        membership_type=CONTRACT_MEMBERSHIP_CODE,
        max_learners=25,
        enrollment_fixed_price=Decimal("10.00"),
    )

    assert contract.get_parent().specific == organization
    assert contract.organization == organization
    assert contract.title == "Spring cohort"
    assert contract.max_learners == 25
    default_variant = contract.variant_options.get()
    assert default_variant.default_variant is True
    assert default_variant.language == "en"


def test_ensure_default_variant_keeps_existing():
    """A contract that has a default variant set keeps it."""

    contract = ContractPageFactory.create()
    existing = contract.variant_options.get(default_variant=True)

    assert ensure_default_variant(contract) == existing
    assert contract.variant_options.count() == 1


def test_add_course_does_not_rerun(mocked_edx):
    """Adding a course twice leaves one contract run, and queues one clone."""

    contract = ContractPageFactory.create()
    course = _source_run().course

    first = add_courseware_to_contract(contract, course)
    second = add_courseware_to_contract(contract, course)

    assert first.runs_added == 1
    assert second.runs_added == 0
    assert contract.get_course_runs().count() == 1
    mocked_edx.assert_called_once()


def test_add_program():
    """Adding a program creates its courses' runs and links the program."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    for _ in range(2):
        program.add_requirement(_source_run().course)

    added = add_courseware_to_contract(contract, program, skip_edx=True)

    assert added.runs_added == 2
    assert added.courses_without_source_run == 0
    assert list(contract.programs) == [program]


def test_add_run_in_another_contract_is_skipped():
    """A run already in another contract stays there and is reported."""

    run = CourseRunFactory.create()
    other_contract = ContractPageFactory.create()
    run.b2b_contracts.add(other_contract)
    contract = ContractPageFactory.create()

    added = add_courseware_to_contract(contract, run)

    assert added.runs_added == 0
    assert str(other_contract) in added.skipped_reason
    assert not run.b2b_contracts.filter(id=contract.id).exists()


@pytest.mark.parametrize("has_enrollments", [True, False])
def test_remove_course(has_enrollments):
    """
    Removing a course closes its contract runs, and unlinks those nobody has
    enrolled in.
    """

    contract = ContractPageFactory.create()
    course = _source_run().course
    add_courseware_to_contract(contract, course, skip_edx=True)
    [run] = contract.get_course_runs()
    if has_enrollments:
        CourseRunEnrollmentFactory.create(run=run)

    [(removed_run, unlinked)] = remove_courseware_from_contract(contract, course)

    removed_run.refresh_from_db()
    assert unlinked is not has_enrollments
    assert removed_run.live is False
    assert contract.get_course_runs().filter(id=run.id).exists() is has_enrollments
    assert not contract.get_products().exists()


def test_remove_run_outside_contract():
    """A run that is not in the contract is not touched."""

    contract = ContractPageFactory.create()
    run = CourseRunFactory.create(live=True)

    assert remove_courseware_from_contract(contract, run) == []
    run.refresh_from_db()
    assert run.live is True


@pytest.mark.parametrize(
    ("membership_type", "price", "max_learners", "expected"),
    [
        (CONTRACT_MEMBERSHIP_MANAGED, None, 5, 0),
        (CONTRACT_MEMBERSHIP_AUTO, None, None, 0),
        (CONTRACT_MEMBERSHIP_AUTO, Decimal("5.00"), None, 2),
        (CONTRACT_MEMBERSHIP_CODE, None, None, 2),
        (CONTRACT_MEMBERSHIP_CODE, None, 3, 6),
    ],
)
def test_expected_enrollment_code_count(membership_type, price, max_learners, expected):
    """Codes are expected per product, times the seat cap when there is one."""

    contract = ContractPageFactory.create(
        membership_type=membership_type,
        enrollment_fixed_price=price,
        max_learners=max_learners,
    )
    for _ in range(2):
        add_courseware_to_contract(contract, _source_run().course, skip_edx=True)

    assert expected_enrollment_code_count(contract) == expected


@pytest.mark.parametrize("dry_run", [True, False])
def test_expire_unused_enrollment_codes(mocker, dry_run):
    """Unused codes leave the contract; a redeemed one stays."""

    mocker.patch("b2b.tasks.queue_contract_sheet_update_post_save.delay")
    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_CODE, max_learners=3
    )
    add_courseware_to_contract(contract, _source_run().course, skip_edx=True)
    ensure_enrollment_codes_exist(contract)
    redeemed = contract.get_discounts().first()
    DiscountContractAttachmentRedemption.objects.create(
        discount=redeemed, contract=contract, user=UserFactory.create()
    )

    expired = expire_unused_enrollment_codes(contract, dry_run=dry_run)

    assert len(expired) == 2
    assert all(deleted for _, deleted in expired)
    assert redeemed.discount_code not in [code for code, _ in expired]
    assert contract.get_discounts().distinct().count() == (3 if dry_run else 1)


def _bilingual_source_course():
    """Create a course that supports en and fr, with a source run for each."""

    run = _source_run()
    CourseSupportedVariantFactory.create(
        variant_object=run.course, language="fr", variant_length="", variant_industry=""
    )
    CourseRunFactory.create(course=run.course, is_source_run=True, language="fr")
    return run.course


def test_variant_coverage():
    """
    Each set lists the contract's courses that support it, whether each has a
    source run for it, and the contract's run for it.
    """

    contract = ContractPageFactory.create()
    french = add_contract_variant_set(contract, language="fr")
    german = add_contract_variant_set(contract, language="de")
    course = _bilingual_source_course()
    CourseSupportedVariantFactory.create(
        variant_object=course, language="de", variant_length="", variant_industry=""
    )
    add_courseware_to_contract(contract, course)
    # Not in the contract, so never listed.
    _bilingual_source_course()

    coverage = get_contract_variant_coverage(contract)

    assert [entry["variant"] for entry in coverage] == [
        contract.default_variant_options,
        french,
        german,
    ]
    for entry, language in zip(coverage[:2], ["en", "fr"]):
        [listed] = entry["courses"]
        assert listed["course"] == course
        assert listed["has_source_run"] is True
        assert listed["contract_run"].language == language
    [listed] = coverage[2]["courses"]
    assert listed["has_source_run"] is False
    assert listed["contract_run"] is None


def test_sync_contract_variants(mocked_edx):
    """
    A set added after the courseware gets its run, and the runs the contract
    already has are left alone.
    """

    contract = ContractPageFactory.create()
    course = _bilingual_source_course()
    french_source = course.courseruns.get(is_source_run=True, language="fr")
    add_courseware_to_contract(contract, course)
    [english_run] = contract.get_course_runs()
    mocked_edx.reset_mock()
    add_contract_variant_set(contract, language="fr")

    synced = sync_contract_variants(contract)

    [french_run] = synced["runs_created"]
    assert french_run.language == "fr"
    assert synced["missing_source_runs"] == []
    assert synced["failed"] == []
    assert set(contract.get_course_runs()) == {english_run, french_run}
    mocked_edx.assert_called_once_with(french_run.id, french_source.courseware_id)

    assert sync_contract_variants(contract)["runs_created"] == []
    assert contract.get_course_runs().count() == 2


def test_sync_contract_variants_covers_program_courses():
    """A program's courses get the new set's runs, including one with no runs yet."""

    contract = ContractPageFactory.create()
    program = ProgramFactory.create()
    course = _bilingual_source_course()
    program.add_requirement(course)
    add_courseware_to_contract(contract, program, skip_edx=True)
    late_course = _bilingual_source_course()
    program.add_requirement(late_course)
    add_contract_variant_set(contract, language="fr")

    synced = sync_contract_variants(contract, skip_edx=True)

    assert sorted(
        (run.course_id, run.language) for run in synced["runs_created"]
    ) == sorted([(course.id, "fr"), (late_course.id, "en"), (late_course.id, "fr")])
    assert contract.get_course_runs().count() == 4


@pytest.mark.parametrize(
    "create_contract_run",
    [{"side_effect": SourceCourseIncompleteError}, {"return_value": []}],
    ids=["raises", "creates_nothing"],
)
def test_sync_contract_variants_reports_what_it_could_not_create(
    mocker, create_contract_run
):
    """
    A course with no source run for a set is reported, an inactive set is
    skipped, and a run that can't be created doesn't stop the others.
    """

    contract = ContractPageFactory.create()
    course = _bilingual_source_course()
    for language in ["de", "es"]:
        CourseSupportedVariantFactory.create(
            variant_object=course,
            language=language,
            variant_length="",
            variant_industry="",
        )
    CourseRunFactory.create(course=course, is_source_run=True, language="es")
    add_courseware_to_contract(contract, course, skip_edx=True)
    french = add_contract_variant_set(contract, language="fr")
    german = add_contract_variant_set(contract, language="de")
    spanish = add_contract_variant_set(contract, language="es")
    update_contract_variant_set(contract, spanish, active=False)
    mocker.patch("b2b.contracts.create_contract_run", **create_contract_run)

    synced = sync_contract_variants(contract, skip_edx=True)

    assert synced == {
        "runs_created": [],
        "missing_source_runs": [{"course": course, "variant": german}],
        "failed": [{"course": course, "variant": french}],
    }


def test_add_variant_set_is_audited():
    """Adding a set records who added what, against the contract's organization."""

    contract = ContractPageFactory.create()
    actor = UserFactory.create()

    variant = add_contract_variant_set(
        contract, language="fr", variant_length="s", b2b_only=True, actor=actor
    )

    assert variant.default_variant is False
    assert variant.b2b_only is True
    audit = OrganizationProvisioningAudit.objects.get()
    assert audit.organization == contract.organization
    assert audit.action == PROVISIONING_ACTION_CONTRACT_VARIANT_ADDED
    assert audit.acting_user == actor
    assert audit.data_after["contract_id"] == contract.id
    assert audit.data_after["variant_id"] == variant.id


@pytest.mark.parametrize("active", [True, False])
def test_add_duplicate_variant_set(active):
    """A set the contract already has can't be added again, active or not."""

    contract = ContractPageFactory.create()
    existing = add_contract_variant_set(contract, language="fr")
    if not active:
        update_contract_variant_set(contract, existing, active=False)

    with pytest.raises(ContractVariantError, match=str(existing.id)) as exc:
        add_contract_variant_set(contract, language="fr")

    assert ("inactive" in str(exc.value)) is not active


@pytest.mark.parametrize(
    "change", [{"active": False}, {"b2b_only": True}], ids=["deactivate", "b2b_only"]
)
def test_default_variant_set_cannot_be_changed(change):
    """The default set always stays active and open outside B2B."""

    contract = ContractPageFactory.create()

    with pytest.raises(ContractVariantError):
        update_contract_variant_set(
            contract, contract.default_variant_options, **change
        )

    assert not OrganizationProvisioningAudit.objects.exists()


def test_deactivated_variant_set():
    """
    An inactive set gets no new runs and its runs leave the contract's course
    list, but stay in the contract.
    """

    contract = ContractPageFactory.create()
    french = add_contract_variant_set(contract, language="fr")
    course = _bilingual_source_course()
    add_courseware_to_contract(contract, course)
    actor = UserFactory.create()

    update_contract_variant_set(contract, french, active=False, actor=actor)

    assert set(contract.get_all_variant_runs().values_list("language", flat=True)) == {
        "en"
    }
    assert set(contract.get_course_runs().values_list("language", flat=True)) == {
        "en",
        "fr",
    }
    audit = OrganizationProvisioningAudit.objects.get(
        action=PROVISIONING_ACTION_CONTRACT_VARIANT_UPDATED
    )
    assert audit.acting_user == actor
    assert audit.data_before["active"] is True
    assert audit.data_after["active"] is False

    other_course = _bilingual_source_course()
    add_courseware_to_contract(contract, other_course)

    assert list(
        contract.get_course_runs()
        .filter(course=other_course)
        .values_list("language", flat=True)
    ) == ["en"]


def test_inactive_default_variant_set_still_filters():
    """
    A default set turned off in the admin still limits new runs to it, rather
    than leaving an empty filter that means every variant the course has.
    """

    contract = ContractPageFactory.create()
    default = contract.default_variant_options
    default.active = False
    default.save()

    add_courseware_to_contract(contract, _bilingual_source_course())

    assert list(contract.get_course_runs().values_list("language", flat=True)) == ["en"]


def test_variant_coverage_reports_newest_contract_run():
    """With two contract runs for one course and variant, the newer is listed."""

    contract = ContractPageFactory.create()
    course = _source_run().course
    add_courseware_to_contract(contract, course)
    add_courseware_to_contract(contract, course, no_reruns=False)
    newest = contract.get_course_runs().order_by("-id").first()

    [entry] = get_contract_variant_coverage(contract)

    assert entry["courses"][0]["contract_run"] == newest


def test_unchanged_variant_set_update_is_not_audited():
    """A PATCH that changes nothing leaves no entry in the change history."""

    contract = ContractPageFactory.create()
    variant = add_contract_variant_set(contract, language="fr")

    update_contract_variant_set(contract, variant, active=True, b2b_only=False)

    assert not OrganizationProvisioningAudit.objects.filter(
        action=PROVISIONING_ACTION_CONTRACT_VARIANT_UPDATED
    ).exists()
