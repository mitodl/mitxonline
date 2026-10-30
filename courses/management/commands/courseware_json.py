"""
Export and import courseware (programs, courses, course runs) as JSON.

This covers the courseware objects themselves and their products. Discounts,
flexible pricing, B2B contracts, certificates, CMS pages, and enrollments are
not included.

Exporting a course includes all of its (non-contract) course runs. Exporting a
course run includes its course, with only that run. Exporting a program includes
its requirements tree, every course in the tree (with their runs), and any
programs the tree references - those nested programs are exported without their
own requirements, so the export doesn't recurse into them.

Importing is idempotent: objects are matched on readable ID / courseware ID, and
existing objects are updated to match the file. The import can optionally
append a suffix to every title and replace the org portion of every courseware
ID (program-v1:MITxT+Program -> program-v1:IMP+Program).

Usage:

    ./manage.py courseware_json export program-v1:MITxT+Program -o program.json
    ./manage.py courseware_json import program.json --org IMP --title-suffix " (Import)"
    ./manage.py courseware_json import program.json --commit
"""

import copy
import json
import re
import sys
from decimal import Decimal

import reversion
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime
from mitol.common.utils import now_in_utc

from courses.models import (
    Course,
    CourseRun,
    Department,
    EnrollmentMode,
    Program,
)
from ecommerce.models import Product
from variants.models import SupportedVariant

EXPORT_FORMAT_VERSION = 1

ORG_KEY_PATTERN = re.compile(r"^(?P<prefix>[^:]+:)(?P<org>[^+]+)(?P<rest>\+.+)$")

COURSE_FIELDS = ("title", "live", "certificates_disabled")
COURSE_RUN_FIELDS = (
    "title",
    "run_tag",
    "has_courseware_url",
    "live",
    "is_self_paced",
    "b2b_only",
    "is_source_run",
    "is_primary_language",
    "language",
    "variant_industry",
    "variant_length",
)
PROGRAM_FIELDS = (
    "title",
    "live",
    "program_type",
    "availability",
    "display_mode",
    "b2b_only",
    "certificates_disabled",
)
COURSE_RUN_DATE_FIELDS = (
    "start_date",
    "end_date",
    "certificate_available_date",
    "enrollment_start",
    "enrollment_end",
    "expiration_date",
    "upgrade_deadline",
)
PROGRAM_DATE_FIELDS = ("start_date", "end_date", "enrollment_start", "enrollment_end")
REQUIREMENT_FIELDS = (
    "node_type",
    "operator",
    "operator_value",
    "title",
    "description",
    "elective_flag",
)


def remap_org(key, org):
    """Replace the org portion of a courseware ID (prefix:ORG+...)."""
    match = ORG_KEY_PATTERN.match(key)
    if not match:
        msg = f"Can't change the org of '{key}': it isn't in the form prefix:org+..."
        raise CommandError(msg)
    return f"{match['prefix']}{org}{match['rest']}"


# ------------------------------------------------------------------ export


def _serialize_dates(obj, fields):
    return {
        field: getattr(obj, field).isoformat() if getattr(obj, field) else None
        for field in fields
    }


def _serialize_enrollment_modes(obj):
    return [
        {
            "mode_slug": mode.mode_slug,
            "mode_display_name": mode.mode_display_name,
            "requires_payment": mode.requires_payment,
        }
        for mode in obj.enrollment_modes.order_by("mode_slug")
    ]


def _serialize_product(obj):
    """Serialize the product for obj, or None if it has none."""
    product = Product.all_objects.filter(
        content_type=ContentType.objects.get_for_model(obj), object_id=obj.id
    ).first()
    if product is None:
        return None
    return {
        "price": str(product.price),
        "description": product.description,
        "is_active": product.is_active,
    }


def _serialize_variant_options(course):
    return [
        {
            "language": sv.language,
            "variant_industry": sv.variant_industry,
            "variant_length": sv.variant_length,
            "b2b_only": sv.b2b_only,
            "default_variant": sv.default_variant,
            "active": sv.active,
        }
        for sv in SupportedVariant.objects.filter(
            content_type=ContentType.objects.get_for_model(Course),
            object_id=course.id,
        ).order_by("id")
    ]


def serialize_run(run):
    """Serialize a course run."""
    return {
        "courseware_id": run.courseware_id,
        **{field: getattr(run, field) for field in COURSE_RUN_FIELDS},
        **_serialize_dates(run, COURSE_RUN_DATE_FIELDS),
        "enrollment_modes": _serialize_enrollment_modes(run),
        "product": _serialize_product(run),
    }


def serialize_course(course, runs=None):
    """
    Serialize a course and its runs.

    Contract runs are B2B data, so they're left out unless passed in explicitly.
    """
    if runs is None:
        runs = (
            CourseRun.all_objects.filter(
                course=course, b2b_contracts__isnull=True, b2b_contract__isnull=True
            )
            .distinct()
            .order_by("id")
        )
    return {
        "readable_id": course.readable_id,
        **{field: getattr(course, field) for field in COURSE_FIELDS},
        "departments": sorted(dept.name for dept in course.departments.all()),
        "variant_options": _serialize_variant_options(course),
        "runs": [serialize_run(run) for run in runs],
    }


def serialize_requirements(node):
    """Serialize the children of a requirements tree node, recursively."""
    return [
        {
            **{field: getattr(child, field) for field in REQUIREMENT_FIELDS},
            "course": child.course.readable_id if child.course else None,
            "required_program": (
                child.required_program.readable_id if child.required_program else None
            ),
            "children": serialize_requirements(child),
        }
        for child in node.get_children().select_related("course", "required_program")
    ]


def serialize_program(program, *, include_requirements):
    """Serialize a program, optionally with its requirements tree."""
    requirements = None
    if include_requirements:
        root = program.get_requirements_root()
        requirements = serialize_requirements(root) if root else []
    return {
        "readable_id": program.readable_id,
        **{field: getattr(program, field) for field in PROGRAM_FIELDS},
        **_serialize_dates(program, PROGRAM_DATE_FIELDS),
        "departments": sorted(dept.name for dept in program.departments.all()),
        "enrollment_modes": _serialize_enrollment_modes(program),
        "product": _serialize_product(program),
        "requirements": requirements,
    }


def _requirement_ids(nodes, key):
    """List the readable IDs under key ("course"/"required_program") in tree order."""

    def walk(nodes):
        for node in nodes:
            if node[key]:
                yield node[key]
            yield from walk(node["children"])

    return list(dict.fromkeys(walk(nodes)))


def export_courseware(courseware_id):
    """Build the export payload for a program, course, or course run."""
    program = Program.objects.filter(readable_id=courseware_id).first()
    course = Course.objects.filter(readable_id=courseware_id).first()
    run = CourseRun.all_objects.filter(courseware_id=courseware_id).first()

    if program:
        root_type = "program"
        program_data = serialize_program(program, include_requirements=True)
        nested_ids = _requirement_ids(program_data["requirements"], "required_program")
        nested = {
            nested_program.readable_id: nested_program
            for nested_program in Program.objects.filter(readable_id__in=nested_ids)
        }
        programs = [program_data] + [
            serialize_program(nested[readable_id], include_requirements=False)
            for readable_id in nested_ids
            if readable_id != program.readable_id
        ]
        course_ids = _requirement_ids(program_data["requirements"], "course")
        by_id = {
            c.readable_id: c for c in Course.objects.filter(readable_id__in=course_ids)
        }
        courses = [serialize_course(by_id[readable_id]) for readable_id in course_ids]
    elif course:
        root_type = "course"
        programs = []
        courses = [serialize_course(course)]
    elif run:
        root_type = "course_run"
        programs = []
        courses = [serialize_course(run.course, runs=[run])]
    else:
        msg = f"No program, course, or course run found with ID '{courseware_id}'."
        raise CommandError(msg)

    return {
        "version": EXPORT_FORMAT_VERSION,
        "exported_at": now_in_utc().isoformat(),
        "root": {"type": root_type, "id": courseware_id},
        "programs": programs,
        "courses": courses,
    }


# ------------------------------------------------------------------ transform


def _transform_requirements(nodes, new_id):
    for node in nodes:
        node["course"] = new_id(node["course"])
        node["required_program"] = new_id(node["required_program"])
        _transform_requirements(node["children"], new_id)


def _transform_object(obj, id_field, new_id, new_title):
    """Change an exported object's ID and title, and its product description to match."""
    old_id = obj[id_field]
    obj[id_field] = new_id(old_id)
    obj["title"] = new_title(obj["title"])
    if obj["product"]:
        obj["product"]["description"] = obj["product"]["description"].replace(
            old_id, obj[id_field]
        )


def transform_payload(data, *, title_suffix=None, org=None):
    """
    Return a copy of the payload with titles and courseware IDs changed.

    Applied to the file's data, not the database, so re-running an import with
    the same options produces the same titles and IDs.
    """
    data = copy.deepcopy(data)

    def new_id(key):
        return remap_org(key, org) if org and key else key

    def new_title(title):
        return f"{title}{title_suffix}" if title_suffix else title

    data["root"]["id"] = new_id(data["root"]["id"])

    for program in data["programs"]:
        _transform_object(program, "readable_id", new_id, new_title)
        if program["requirements"] is not None:
            _transform_requirements(program["requirements"], new_id)

    for course in data["courses"]:
        course["readable_id"] = new_id(course["readable_id"])
        course["title"] = new_title(course["title"])
        for run in course["runs"]:
            _transform_object(run, "courseware_id", new_id, new_title)

    return data


# ------------------------------------------------------------------ import


class Command(BaseCommand):
    """Export and import courseware as JSON."""

    help = "Export or import a program, course, or course run as JSON."

    def add_arguments(self, parser):
        """Add command line arguments."""

        subparsers = parser.add_subparsers(
            title="Task",
            dest="subcommand",
            required=True,
        )

        export_parser = subparsers.add_parser(
            "export",
            help="Export a program, course, or course run to JSON.",
        )
        export_parser.add_argument(
            "courseware_id",
            type=str,
            help="The readable ID of the program or course, or the course run's courseware ID.",
        )
        export_parser.add_argument(
            "-o",
            "--output",
            type=str,
            help="Write the export to this file. (Default is stdout.)",
        )

        import_parser = subparsers.add_parser(
            "import",
            help="Import courseware from a JSON export file.",
        )
        import_parser.add_argument(
            "input",
            type=str,
            help="Path to the JSON export file, or '-' to read from stdin.",
        )
        import_parser.add_argument(
            "--commit",
            action="store_false",
            dest="dry_run",
            default=True,
            help="Actually import the courseware. (Default is a dry run.)",
        )
        import_parser.add_argument(
            "--title-suffix",
            type=str,
            help="Append this to every program, course, and course run title.",
        )
        import_parser.add_argument(
            "--org",
            type=str,
            help=(
                "Replace the org in every courseware ID with this "
                "(program-v1:MITxT+Program becomes program-v1:<org>+Program)."
            ),
        )

    def handle_export(self, *args, **kwargs):  # noqa: ARG002
        """Write the export payload to stdout or a file."""
        courseware_id = kwargs.pop("courseware_id")
        output_path = kwargs.pop("output", None)

        output = json.dumps(export_courseware(courseware_id), indent=2)

        if output_path:
            with open(output_path, "w") as f:  # noqa: PTH123
                f.write(output)
            self.stderr.write(
                self.style.SUCCESS(f"Exported '{courseware_id}' to {output_path}")
            )
        else:
            self.stdout.write(output)

    def _report(self, label, readable_id, *, created, changed):
        if created:
            self.stdout.write(self.style.SUCCESS(f"  Created {label}: {readable_id}"))
        elif changed:
            self.stdout.write(f"  Updated {label}: {readable_id}")
        else:
            self.stdout.write(f"  Unchanged {label}: {readable_id}")

    def _upsert(self, model_cls, lookup, values):
        """
        Get or create the object, then update it to match values.

        Only saves when something differs, so re-imports don't re-trigger the
        save signals (Fastly purges, edX upgrade deadline pushes).

        Returns the object, whether it was created, and whether it was changed.
        """
        manager = getattr(model_cls, "all_objects", model_cls.objects)
        obj = manager.filter(**lookup).first()
        if obj is None:
            return manager.create(**lookup, **values), True, False

        changed = [
            field for field, value in values.items() if getattr(obj, field) != value
        ]
        for field in changed:
            setattr(obj, field, values[field])
        if changed:
            obj.save()
        return obj, False, bool(changed)

    def _set_m2m(self, related_manager, objs):
        """Set an M2M relation, returning True if it changed."""
        if set(related_manager.all()) == set(objs):
            return False
        related_manager.set(objs)
        return True

    def _departments(self, names):
        return [Department.objects.get_or_create(name=name)[0] for name in names]

    def _enrollment_modes(self, modes_data):
        return [
            EnrollmentMode.objects.get_or_create(
                mode_slug=mode["mode_slug"],
                defaults={
                    "mode_display_name": mode["mode_display_name"],
                    "requires_payment": mode["requires_payment"],
                },
            )[0]
            for mode in modes_data
        ]

    def _import_product(self, obj, product_data):
        """
        Create or update the product for obj. A missing product is left alone.

        Checkout reads the price from the product's latest version, so the save
        has to happen inside a revision.
        """
        if product_data is None:
            return False
        with reversion.create_revision():
            _, created, changed = self._upsert(
                Product,
                {
                    "content_type": ContentType.objects.get_for_model(obj),
                    "object_id": obj.id,
                },
                {
                    "price": Decimal(product_data["price"]),
                    "description": product_data["description"],
                    "is_active": product_data["is_active"],
                },
            )
        return created or changed

    def _import_variant_options(self, course, variants_data):
        course_variants = SupportedVariant.objects.filter(
            content_type=ContentType.objects.get_for_model(Course),
            object_id=course.id,
        )
        # Only one default variant is allowed per course, so clear any default
        # the file doesn't name before upserting the file's.
        changed = False
        for variant in variants_data:
            if variant["default_variant"]:
                changed = bool(
                    course_variants.filter(default_variant=True)
                    .exclude(
                        language=variant["language"],
                        variant_industry=variant["variant_industry"],
                        variant_length=variant["variant_length"],
                    )
                    .update(default_variant=False)
                )

        for variant in variants_data:
            _, created, updated = self._upsert(
                SupportedVariant,
                {
                    "content_type": ContentType.objects.get_for_model(Course),
                    "object_id": course.id,
                    "language": variant["language"],
                    "variant_industry": variant["variant_industry"],
                    "variant_length": variant["variant_length"],
                },
                {
                    "b2b_only": variant["b2b_only"],
                    "default_variant": variant["default_variant"],
                    "active": variant["active"],
                },
            )
            changed = changed or created or updated
        return changed

    def _import_run(self, course, run_data):
        existing = CourseRun.all_objects.filter(
            courseware_id=run_data["courseware_id"]
        ).first()
        if existing and existing.course_id != course.id:
            msg = (
                f"Course run '{run_data['courseware_id']}' already exists under "
                f"course '{existing.course.readable_id}', not '{course.readable_id}'."
            )
            raise CommandError(msg)

        run, created, changed = self._upsert(
            CourseRun,
            {"courseware_id": run_data["courseware_id"]},
            {
                "course": course,
                **{field: run_data[field] for field in COURSE_RUN_FIELDS},
                **{
                    field: parse_datetime(run_data[field]) if run_data[field] else None
                    for field in COURSE_RUN_DATE_FIELDS
                },
            },
        )
        changed = (
            self._set_m2m(
                run.enrollment_modes,
                self._enrollment_modes(run_data["enrollment_modes"]),
            )
            or changed
        )
        changed = self._import_product(run, run_data["product"]) or changed
        self._report("course run", run.courseware_id, created=created, changed=changed)

    def _import_course(self, course_data):
        course, created, changed = self._upsert(
            Course,
            {"readable_id": course_data["readable_id"]},
            {field: course_data[field] for field in COURSE_FIELDS},
        )
        changed = (
            self._set_m2m(
                course.departments, self._departments(course_data["departments"])
            )
            or changed
        )
        changed = (
            self._import_variant_options(course, course_data["variant_options"])
            or changed
        )
        self._report("course", course.readable_id, created=created, changed=changed)

        for run_data in course_data["runs"]:
            self._import_run(course, run_data)

        return course

    def _import_program(self, program_data):
        program, created, changed = self._upsert(
            Program,
            {"readable_id": program_data["readable_id"]},
            {
                **{field: program_data[field] for field in PROGRAM_FIELDS},
                **{
                    field: (
                        parse_datetime(program_data[field])
                        if program_data[field]
                        else None
                    )
                    for field in PROGRAM_DATE_FIELDS
                },
            },
        )
        changed = (
            self._set_m2m(
                program.departments, self._departments(program_data["departments"])
            )
            or changed
        )
        changed = (
            self._set_m2m(
                program.enrollment_modes,
                self._enrollment_modes(program_data["enrollment_modes"]),
            )
            or changed
        )
        changed = self._import_product(program, program_data["product"]) or changed
        self._report("program", program.readable_id, created=created, changed=changed)
        return program

    def _add_requirements(self, parent, nodes, courses, programs):
        for node in nodes:
            child = parent.add_child(
                **{field: node[field] for field in REQUIREMENT_FIELDS},
                course=courses[node["course"]] if node["course"] else None,
                required_program=(
                    programs[node["required_program"]]
                    if node["required_program"]
                    else None
                ),
            )
            self._add_requirements(child, node["children"], courses, programs)

    def _import_requirements(self, program, requirements, courses, programs):
        """
        Replace the program's requirements tree if it differs from the file.

        Rebuilding clears any track a learner chose in this program, so an
        unchanged tree is left alone.
        """
        root = program.get_requirements_root(for_update=True)
        if root is None:
            # Program.save() creates the root node if it's missing.
            program.save()
            root = program.get_requirements_root(for_update=True)
        if serialize_requirements(root) == requirements:
            self.stdout.write(f"  Unchanged requirements: {program.readable_id}")
            return

        for child in root.get_children():
            child.delete()
        root = program.get_requirements_root()
        self._add_requirements(root, requirements, courses, programs)
        self.stdout.write(
            self.style.SUCCESS(f"  Rebuilt requirements: {program.readable_id}")
        )

    def _validate_requirement_refs(self, data):
        """Make sure every course/program a tree references is in the file."""
        course_ids = {course["readable_id"] for course in data["courses"]}
        program_ids = {program["readable_id"] for program in data["programs"]}
        for program in data["programs"]:
            requirements = program["requirements"] or []
            missing = [
                *(
                    readable_id
                    for readable_id in _requirement_ids(requirements, "course")
                    if readable_id not in course_ids
                ),
                *(
                    readable_id
                    for readable_id in _requirement_ids(
                        requirements, "required_program"
                    )
                    if readable_id not in program_ids
                ),
            ]
            if missing:
                msg = (
                    f"Program '{program['readable_id']}' requires courseware that "
                    f"isn't in the file: {', '.join(missing)}"
                )
                raise CommandError(msg)

    def run_import(self, data):
        """Import the (already transformed) payload. Call inside a transaction."""
        self._validate_requirement_refs(data)

        self.stdout.write("\nCourses")
        courses = {
            course_data["readable_id"]: self._import_course(course_data)
            for course_data in data["courses"]
        }

        self.stdout.write("\nPrograms")
        programs = {
            program_data["readable_id"]: self._import_program(program_data)
            for program_data in data["programs"]
        }

        self.stdout.write("\nRequirements")
        for program_data in data["programs"]:
            if program_data["requirements"] is not None:
                self._import_requirements(
                    programs[program_data["readable_id"]],
                    program_data["requirements"],
                    courses,
                    programs,
                )

    def handle_import(self, *args, **kwargs):  # noqa: ARG002
        """Import courseware from a JSON export file."""
        input_path = kwargs.pop("input")
        dry_run = kwargs.pop("dry_run", True)

        if input_path == "-":
            data = json.load(sys.stdin)
        else:
            with open(input_path) as f:  # noqa: PTH123
                data = json.load(f)

        if data.get("version") != EXPORT_FORMAT_VERSION:
            msg = (
                f"Unsupported export format version {data.get('version')!r}, "
                f"expected {EXPORT_FORMAT_VERSION}."
            )
            raise CommandError(msg)

        data = transform_payload(
            data,
            title_suffix=kwargs.pop("title_suffix", None),
            org=kwargs.pop("org", None),
        )

        self.stdout.write(
            f"Importing {data['root']['type']} '{data['root']['id']}' "
            f"(exported {data.get('exported_at', 'unknown date')})"
            + (" [DRY RUN]" if dry_run else "")
        )

        with transaction.atomic():
            self.run_import(data)
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        "\nDry run - rolling back. Pass --commit to apply changes."
                    )
                )
                transaction.set_rollback(True)
                return

        self.stdout.write(self.style.SUCCESS("\nImport complete."))

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Dispatch to the subcommand."""
        subcommand = kwargs.pop("subcommand")
        if subcommand == "export":
            self.handle_export(**kwargs)
        elif subcommand == "import":
            self.handle_import(**kwargs)
