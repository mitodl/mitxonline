"""Tests for the check_contract_variant command."""

from io import StringIO

import pytest
from django.core.management import call_command

from b2b.contracts import add_contract_variant_set, add_courseware_to_contract
from b2b.factories import ContractPageFactory
from courses.factories import CourseRunFactory
from variants.factories import CourseSupportedVariantFactory

pytestmark = [pytest.mark.django_db]


def test_reports_each_course_per_variant_set(mocker):
    """Each set lists the contract's courses and why one has no run for it."""

    mocker.patch("openedx.tasks.clone_courserun.delay")
    contract = ContractPageFactory.create()
    for language in ["fr", "de", "es"]:
        add_contract_variant_set(contract, language=language)
    source_run = CourseRunFactory.create(
        is_source_run=True, language="en", is_primary_language=True
    )
    course = source_run.course
    for language in ["fr", "de"]:
        CourseSupportedVariantFactory.create(
            variant_object=course,
            language=language,
            variant_length="",
            variant_industry="",
        )
    CourseRunFactory.create(course=course, is_source_run=True, language="fr")
    add_courseware_to_contract(contract, course, skip_edx=True)
    english_run, french_run = contract.get_course_runs().order_by("id")
    french_run.b2b_contracts.remove(contract)
    out = StringIO()

    call_command("check_contract_variant", str(contract.id), stdout=out, no_color=True)

    lines = [line.strip() for line in out.getvalue().splitlines()]
    assert f"{course.readable_id}: {english_run.courseware_id}" in lines
    assert lines.count(f"{course.readable_id}: NO RUN") == 1
    assert lines.count(f"{course.readable_id}: NO RUN, NO SOURCE RUN") == 1
    assert lines.count(f"{course.readable_id}: NOT IN THE COURSE VARIANTS") == 1


@pytest.mark.parametrize("fix_default", [True, False])
def test_contract_with_no_default_variant_set(fix_default):
    """Without a default set nothing is reported, unless --fix-default adds one."""

    contract = ContractPageFactory.create()
    contract.variant_options.all().delete()
    args = ["--fix-default"] if fix_default else []
    out = StringIO()

    call_command(
        "check_contract_variant",
        str(contract.id),
        *args,
        stdout=out,
        stderr=StringIO(),
        no_color=True,
    )

    assert contract.variant_options.filter(default_variant=True).exists() is fix_default
    assert ("Language = " in out.getvalue()) is fix_default
