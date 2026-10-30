"""Tests for the b2b_contract command."""

import pytest
from django.core.management import call_command

from b2b.constants import CONTRACT_MEMBERSHIP_MANAGED
from b2b.contracts import add_courseware_to_contract
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.management.commands import b2b_contract
from b2b.models import ContractPage, OrganizationIndexPage
from courses.factories import CourseFactory, CourseRunFactory, ProgramFactory
from courses.models import Program

pytestmark = [pytest.mark.django_db]


def test_export_import_contract_with_nested_programs(mocker, tmp_path):
    """
    A contract whose program only requires other programs exports them, and
    importing the export rebuilds them and creates their courses' contract runs.
    """
    # The CMS bootstrap expects one root page; the factories here make several.
    mocker.patch.object(
        b2b_contract.Command,
        "_ensure_cms_infrastructure",
        side_effect=OrganizationIndexPage.objects.first,
    )

    def make_course(key):
        course = CourseFactory.create(readable_id=f"course-v1:EXPORTED+{key}")
        CourseRunFactory.create(
            course=course,
            courseware_id=f"course-v1:EXPORTED+{key}+SOURCE",
            is_source_run=True,
            language="en",
            is_primary_language=True,
        )
        return course

    root = ProgramFactory.create(readable_id="program-v1:EXPORTED+Root")
    module = ProgramFactory.create(
        readable_id="program-v1:EXPORTED+Module", display_mode="course"
    )
    elective_module = ProgramFactory.create(readable_id="program-v1:EXPORTED+Elective")
    root.add_program_requirement(module)
    root.add_program_elective(elective_module)
    module.add_requirement(make_course("A"))
    elective_module.add_requirement(make_course("B"))
    contract = ContractPageFactory.create()
    add_courseware_to_contract(contract, root, skip_edx=True)
    assert contract.get_course_runs().count() == 2

    export_path = tmp_path / "contract.json"
    call_command("b2b_contract", "export", str(contract.id), "--output", export_path)
    # Rename the courseware so the import creates it, as on a fresh instance.
    import_path = tmp_path / "renamed.json"
    import_path.write_text(export_path.read_text().replace("EXPORTED+", "IMPORTED+"))
    call_command(
        "b2b_contract", "import", str(import_path), "--commit", "--slug", "imported"
    )

    imported = ContractPage.objects.get(slug="imported")
    imported_root = Program.objects.get(readable_id="program-v1:IMPORTED+Root")
    imported_module = Program.objects.get(readable_id="program-v1:IMPORTED+Module")
    assert list(imported.programs) == [imported_root]
    assert imported_root.required_programs == [imported_module]
    assert [p.readable_id for p in imported_root.elective_programs] == [
        "program-v1:IMPORTED+Elective"
    ]
    assert imported_module.display_mode == "course"
    assert sorted(run.course.readable_id for run in imported.get_course_runs()) == [
        "course-v1:IMPORTED+A",
        "course-v1:IMPORTED+B",
    ]


def test_import_contract_ignores_same_slug_in_another_org():
    """Importing creates the contract in its org even if another org uses the slug."""
    elsewhere = ContractPageFactory.create()
    org = OrganizationPageFactory.create()

    contract = b2b_contract.Command()._import_contract(  # noqa: SLF001
        org,
        {"name": "Imported", "membership_type": CONTRACT_MEMBERSHIP_MANAGED},
        elsewhere.slug,
    )

    assert contract.id != elsewhere.id
    assert contract.organization == org
