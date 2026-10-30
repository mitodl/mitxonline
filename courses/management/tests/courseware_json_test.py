"""Tests for the courseware_json management command."""

import json

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from reversion.models import Version

from b2b.factories import ContractPageFactory
from courses.factories import CourseFactory, CourseRunFactory, ProgramFactory
from courses.management.commands.courseware_json import (
    export_courseware,
    remap_org,
    serialize_requirements,
)
from courses.models import Course, CourseRun, Program, ProgramRequirement
from ecommerce.factories import ProductFactory, ProgramProductFactory
from ecommerce.models import Product
from variants.factories import CourseSupportedVariantFactory
from variants.models import SupportedVariant

pytestmark = pytest.mark.django_db


@pytest.fixture
def program_tree():
    """A program with a required course, an elective course, and a nested program."""
    program = ProgramFactory.create(readable_id="program-v1:MITxT+Program")
    required = CourseFactory.create(readable_id="course-v1:MITxT+Required")
    elective = CourseFactory.create(readable_id="course-v1:MITxT+Elective")
    nested = ProgramFactory.create(readable_id="program-v1:MITxT+Nested")
    nested_only = CourseFactory.create(readable_id="course-v1:MITxT+NestedOnly")
    nested.add_requirement(nested_only)

    required_run = CourseRunFactory.create(
        course=required, courseware_id="course-v1:MITxT+Required+1T2026"
    )
    CourseRunFactory.create(
        course=elective, courseware_id="course-v1:MITxT+Elective+1T2026"
    )
    ProductFactory.create(
        purchasable_object=required_run,
        price="100.00",
        description=required_run.courseware_id,
    )
    ProgramProductFactory.create(purchasable_object=program, price="500.00")

    program.add_requirement(required)
    program.add_elective(elective)
    program.add_program_requirement(nested)
    return program


def _write_export(tmp_path, courseware_id):
    path = tmp_path / "export.json"
    call_command("courseware_json", "export", courseware_id, "-o", str(path))
    return path


def test_remap_org():
    """remap_org replaces only the org segment."""
    assert remap_org("program-v1:MITxT+Program", "IMP") == "program-v1:IMP+Program"
    assert (
        remap_org("course-v1:MITxT+6.00x+1T2026", "IMP") == "course-v1:IMP+6.00x+1T2026"
    )
    with pytest.raises(CommandError):
        remap_org("no-org-here", "IMP")


def test_export_program(program_tree):
    """A program export has its tree courses and nested programs, without recursing."""
    data = export_courseware(program_tree.readable_id)

    assert data["root"] == {"type": "program", "id": program_tree.readable_id}
    assert [p["readable_id"] for p in data["programs"]] == [
        "program-v1:MITxT+Program",
        "program-v1:MITxT+Nested",
    ]
    assert data["programs"][1]["requirements"] is None
    assert [c["readable_id"] for c in data["courses"]] == [
        "course-v1:MITxT+Required",
        "course-v1:MITxT+Elective",
    ]
    assert data["programs"][0]["product"]["price"] == "500.00"
    assert data["courses"][0]["runs"][0]["product"]["price"] == "100.00"


def test_export_course_skips_contract_runs():
    """A course export has its runs, minus contract runs."""
    course = CourseFactory.create()
    run = CourseRunFactory.create(course=course)
    contract_run = CourseRunFactory.create(course=course, b2b_only=True)
    contract_run.b2b_contracts.add(ContractPageFactory.create())

    data = export_courseware(course.readable_id)

    assert data["root"]["type"] == "course"
    assert [r["courseware_id"] for r in data["courses"][0]["runs"]] == [
        run.courseware_id
    ]


def test_export_course_run():
    """A course run export has its course with only that run."""
    run = CourseRunFactory.create()
    CourseRunFactory.create(course=run.course)

    data = export_courseware(run.courseware_id)

    assert data["root"]["type"] == "course_run"
    assert data["programs"] == []
    assert [c["readable_id"] for c in data["courses"]] == [run.course.readable_id]
    assert [r["courseware_id"] for r in data["courses"][0]["runs"]] == [
        run.courseware_id
    ]


def test_export_not_found():
    """Exporting an unknown ID is an error."""
    with pytest.raises(CommandError):
        export_courseware("course-v1:Nope+Nope")


def test_import_with_org_and_title_suffix(tmp_path, program_tree):
    """Importing with --org and --title-suffix makes copies with new IDs and titles."""
    path = _write_export(tmp_path, program_tree.readable_id)

    call_command(
        "courseware_json", "import", str(path), "--commit", "--org", "IMP",
        "--title-suffix", " (Copy)",
    )  # fmt: skip

    imported = Program.objects.get(readable_id="program-v1:IMP+Program")
    assert imported.title == f"{program_tree.title} (Copy)"
    nested = Program.objects.get(readable_id="program-v1:IMP+Nested")
    # Nested programs come across without their own requirements.
    assert serialize_requirements(nested.get_requirements_root()) == []

    required = Course.objects.get(readable_id="course-v1:IMP+Required")
    run = CourseRun.all_objects.get(courseware_id="course-v1:IMP+Required+1T2026")
    assert run.course == required
    assert run.title.endswith(" (Copy)")
    product = Product.objects.get(courserunproducts=run)
    assert str(product.price) == "100.00"
    assert product.description == run.courseware_id
    # Checkout reads the price from the product's latest version.
    assert Version.objects.get_for_object(product).exists()
    assert str(Product.objects.get(programs=imported).price) == "500.00"

    # The tree matches the source's, with the remapped IDs.
    expected = json.loads(
        json.dumps(
            serialize_requirements(program_tree.get_requirements_root())
        ).replace("MITxT", "IMP")
    )
    assert serialize_requirements(imported.get_requirements_root()) == expected
    source = Course.objects.get(readable_id="course-v1:MITxT+Required")
    assert required.title == f"{source.title} (Copy)"

    # The source objects are untouched.
    assert (
        not Course.objects.filter(title__endswith=" (Copy)")
        .exclude(readable_id__startswith="course-v1:IMP+")
        .exists()
    )


def test_import_is_idempotent(tmp_path, program_tree):
    """Importing the same file twice leaves the second import with nothing to do."""
    path = _write_export(tmp_path, program_tree.readable_id)
    args = ("courseware_json", "import", str(path), "--commit", "--org", "IMP")

    call_command(*args)
    counts = (
        Program.objects.count(),
        Course.objects.count(),
        CourseRun.all_objects.count(),
        Product.all_objects.count(),
        ProgramRequirement.objects.count(),
    )
    node_ids = set(ProgramRequirement.objects.values_list("id", flat=True))

    call_command(*args)

    assert counts == (
        Program.objects.count(),
        Course.objects.count(),
        CourseRun.all_objects.count(),
        Product.all_objects.count(),
        ProgramRequirement.objects.count(),
    )
    # An unchanged tree isn't rebuilt.
    assert set(ProgramRequirement.objects.values_list("id", flat=True)) == node_ids


def test_import_updates_existing(tmp_path):
    """Importing over existing courseware updates it to match the file."""
    run = CourseRunFactory.create(title="Original")
    ProductFactory.create(purchasable_object=run, price="10.00")
    path = _write_export(tmp_path, run.course.readable_id)

    run.title = "Changed"
    run.save()
    Product.objects.filter(courserunproducts=run).update(price="20.00")

    call_command("courseware_json", "import", str(path), "--commit")

    run.refresh_from_db()
    assert run.title == "Original"
    product = Product.objects.get(courserunproducts=run)
    assert str(product.price) == "10.00"
    assert (
        Version.objects.get_for_object(product).first().field_dict["price"]
        == product.price
    )


def test_import_moves_default_variant(tmp_path):
    """The file's default variant replaces a different existing default."""
    # CourseFactory makes an "en" default variant.
    course = CourseFactory.create()
    CourseSupportedVariantFactory.create(
        variant_object=course,
        language="zh",
        variant_industry="",
        variant_length="",
        default_variant=False,
        b2b_only=False,
    )
    path = _write_export(tmp_path, course.readable_id)

    SupportedVariant.objects.filter(language="en").update(default_variant=False)
    SupportedVariant.objects.filter(language="zh").update(default_variant=True)

    call_command("courseware_json", "import", str(path), "--commit")

    assert list(
        SupportedVariant.objects.filter(default_variant=True).values_list(
            "language", flat=True
        )
    ) == ["en"]


def test_import_dry_run(tmp_path):
    """Without --commit, nothing is saved."""
    run = CourseRunFactory.create()
    path = _write_export(tmp_path, run.courseware_id)

    call_command("courseware_json", "import", str(path), "--org", "IMP")

    assert not Course.objects.filter(readable_id__startswith="course-v1:IMP+").exists()


def test_import_rejects_run_under_another_course(tmp_path):
    """A run ID that already belongs to a different course is an error."""
    run = CourseRunFactory.create()
    path = _write_export(tmp_path, run.courseware_id)
    data = json.loads(path.read_text())
    data["courses"][0]["readable_id"] = "course-v1:PyT+Other"
    path.write_text(json.dumps(data))

    with pytest.raises(CommandError, match="already exists under course"):
        call_command("courseware_json", "import", str(path), "--commit")
