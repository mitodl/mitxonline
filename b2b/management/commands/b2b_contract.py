"""Management command for B2B contracts."""

import json
import logging
import sys
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from mitol.common.utils import now_in_utc

from b2b.constants import (
    CONTRACT_MEMBERSHIP_CHOICES,
)
from b2b.exceptions import SourceCourseIncompleteError
from b2b.models import (
    ContractPage,
    ContractProgramItem,
    OrganizationIndexPage,
    OrganizationPage,
)
from courses.models import (
    Course,
    CourseRun,
    Department,
    EnrollmentMode,
    Program,
    ProgramRequirement,
    ProgramRequirementNodeType,
)
from variants.models import SupportedVariant

log = logging.getLogger(__name__)


def _serialize_date(d):
    return d.isoformat() if d is not None else None


def _serialize_run(run, *, force_is_source_run=False, language_override=None):
    """Serialize a CourseRun to a dict suitable for the export JSON.

    language_override: pass the course's default-variant language when the run
    itself carries NULL/empty so the import has the correct value for variant
    matching in _get_source_runs_for_course.
    """
    return {
        "courseware_id": run.courseware_id,
        "run_tag": run.run_tag,
        "title": run.title,
        "is_source_run": True if force_is_source_run else run.is_source_run,
        "is_primary_language": run.is_primary_language,
        "language": language_override
        if language_override is not None
        else (run.language or ""),
        "variant_industry": run.variant_industry or "",
        "variant_length": run.variant_length or "",
        "start_date": _serialize_date(run.start_date),
        "end_date": _serialize_date(run.end_date),
        "enrollment_start": _serialize_date(run.enrollment_start),
        "enrollment_end": _serialize_date(run.enrollment_end),
        "live": run.live,
        "is_self_paced": run.is_self_paced,
        "has_courseware_url": run.has_courseware_url,
        "enrollment_modes": [m.mode_slug for m in run.enrollment_modes.all()],
    }


def _serialize_variant_options(qs):
    return [
        {
            "language": sv.language,
            "variant_industry": sv.variant_industry,
            "variant_length": sv.variant_length,
            "b2b_only": sv.b2b_only,
            "default_variant": sv.default_variant,
        }
        for sv in qs
    ]


class Command(BaseCommand):
    """Manage B2B contracts."""

    help = "Manage B2B contracts."

    def add_arguments(self, parser):
        """Add command line arguments."""

        subparsers = parser.add_subparsers(
            title="Task",
            dest="subcommand",
            required=True,
        )

        create_parser = subparsers.add_parser(
            "create",
            help="Create a new contract.",
        )
        create_parser.add_argument(
            "organization",
            type=str,
            help="The name (or org key) of the organization.",
        )
        create_parser.add_argument(
            "contract_name",
            type=str,
            help="The name of the contract.",
        )
        create_parser.add_argument(
            "membership_type",
            type=str,
            help="The membership type for this contract.",
            choices=[value[0] for value in CONTRACT_MEMBERSHIP_CHOICES],
        )
        create_parser.add_argument(
            "--description",
            type=str,
            help="Description of the contract.",
        )
        create_parser.add_argument(
            "--start",
            type=str,
            help="The start date of the contract.",
        )
        create_parser.add_argument(
            "--end",
            type=str,
            help="The end date of the contract.",
        )
        create_parser.add_argument(
            "--create",
            action="store_true",
            help="Create an organization if it does not exist.",
        )
        create_parser.add_argument(
            "--org-key",
            type=str,
            help="The org key to use for the new organization.",
        )
        create_parser.add_argument(
            "--max-learners",
            type=int,
            help="The maximum number of learners for this contract.",
            default=None,
        )
        create_parser.add_argument(
            "--price",
            type=Decimal,
            help="The fixed price for enrollment under this contract.",
            default=None,
        )

        modify_parser = subparsers.add_parser(
            "modify",
            help="Modify an existing contract.",
        )
        modify_parser.add_argument(
            "contract_id",
            type=int,
            help="The ID of the contract to modify.",
        )
        modify_parser.add_argument(
            "--start",
            type=str,
            help="Change the start date of the contract.",
        )
        modify_parser.add_argument(
            "--end",
            type=str,
            help="Change the end date of the contract.",
        )
        modify_parser.add_argument(
            "--active",
            action="store_true",
            help="Set the contract as active.",
        )
        modify_parser.add_argument(
            "--inactive",
            "--delete",
            action="store_true",
            help="Set the contract as inactive.",
            dest="inactive",
        )
        modify_parser.add_argument(
            "--max-learners",
            type=int,
            help="The maximum number of learners for this contract.",
            default=None,
        )
        modify_parser.add_argument(
            "--price",
            type=Decimal,
            help="The fixed price for enrollment under this contract.",
            default=None,
        )
        modify_parser.add_argument(
            "--no-price",
            action="store_true",
            help="Clear the price for this contract (makes enrollments free).",
        )
        modify_parser.add_argument(
            "--no-learner-cap",
            action="store_true",
            help="Clear the learner limit.",
        )
        modify_parser.add_argument(
            "--no-start-date",
            action="store_true",
            help="Clear the start date.",
        )
        modify_parser.add_argument(
            "--no-end-date",
            action="store_true",
            help="Clear the end date.",
        )

        export_parser = subparsers.add_parser(
            "export",
            help="Export a contract and its courseware structure to JSON.",
        )
        export_parser.add_argument(
            "contract_id",
            type=str,
            help="The ID or slug of the contract to export.",
        )
        export_parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Write JSON to this file path instead of stdout.",
        )

        import_parser = subparsers.add_parser(
            "import",
            help="Import a contract from a JSON export file.",
        )
        import_parser.add_argument(
            "input",
            type=str,
            help="Path to the JSON export file, or '-' to read from stdin.",
        )
        import_parser.add_argument(
            "--commit",
            action="store_false",
            default=True,
            dest="dry_run",
            help="Actually import the contract. (Default is a dry run.)",
        )
        import_parser.add_argument(
            "--slug",
            type=str,
            default=None,
            help="Override the contract slug (useful when importing to the same instance).",
        )
        import_parser.add_argument(
            "--skip-runs",
            action="store_true",
            help="Set up the contract structure but skip creating contract runs.",
        )

        return super().add_arguments(parser)

    def handle_create(self, *args, **kwargs):  # noqa: ARG002
        """Handle the create subcommand."""
        organization_name = kwargs.pop("organization")
        contract_name = kwargs.pop("contract_name")
        membership_type = kwargs.pop("membership_type")
        description = kwargs.pop("description")
        start_date = kwargs.pop("start")
        end_date = kwargs.pop("end")
        create_organization = kwargs.pop("create")
        max_learners = kwargs.pop("max_learners")
        price = kwargs.pop("price")
        new_org_key = kwargs.pop("org_key")

        self.stdout.write(
            f"Creating contract '{contract_name}' for organization '{organization_name}'"
        )

        org = OrganizationPage.objects.filter(
            Q(name=organization_name) | Q(org_key=organization_name)
        ).first()

        log.info("Got organization %s", org)

        if not org and create_organization:
            if not new_org_key:
                msg = f"To create '{organization_name}', you must supply an org key."
                raise CommandError(msg)

            parent = OrganizationIndexPage.objects.first()
            org = OrganizationPage(name=organization_name, org_key=new_org_key)
            parent.add_child(instance=org)
            org.save()
            parent.save()
            org.refresh_from_db()
            self.stdout.write(f"Created organization '{organization_name}'")
        elif not org:
            msg = f"Organization '{organization_name}' does not exist. Use --create to create it."
            raise CommandError(msg)

        contract = ContractPage(
            name=contract_name,
            description=description or "",
            membership_type=membership_type,
            organization=org,
            contract_start=start_date,
            contract_end=end_date,
            max_learners=max_learners,
            enrollment_fixed_price=price,
        )
        org.add_child(instance=contract)
        contract.save()
        self.stdout.write(
            f"Created contract '{contract_name}' for organization '{organization_name}'"
        )

    def handle_modify(self, *args, **kwargs):  # noqa: ARG002, C901
        """Handle the modify subcommand."""
        contract_id = kwargs.pop("contract_id")
        start_date = kwargs.pop("start")
        end_date = kwargs.pop("end")
        active = kwargs.pop("active")
        inactive = kwargs.pop("inactive")
        max_learners = kwargs.pop("max_learners")
        price = kwargs.pop("price")
        no_price = kwargs.pop("no_price")
        no_learner_cap = kwargs.pop("no_learner_cap")
        no_start_date = kwargs.pop("no_start_date")
        no_end_date = kwargs.pop("no_end_date")

        contract = ContractPage.objects.filter(id=contract_id).first()
        if not contract:
            msg = f"Contract with ID '{contract_id}' does not exist."
            raise CommandError(msg)

        if start_date:
            contract.contract_start = start_date
        if end_date:
            contract.contract_end = end_date
        if active:
            contract.active = True
        if inactive:
            contract.active = False
        if max_learners is not None:
            contract.max_learners = max_learners
        if price is not None:
            contract.enrollment_fixed_price = price

        if no_price:
            contract.enrollment_fixed_price = None
        if no_learner_cap:
            contract.max_learners = None
        if no_start_date:
            contract.contract_start = None
        if no_end_date:
            contract.contract_end = None

        contract.save()
        self.stdout.write(f"Modified contract with ID '{contract_id}'")

    def handle_export(self, *args, **kwargs):  # noqa: ARG002
        """Serialize a contract and its courseware blueprint to JSON.

        Exports the organization, contract metadata, programs, courses, and
        source runs.  Contract-specific runs are intentionally excluded; the
        import command regenerates them via create_contract_run so that the
        normal run-creation logic (key generation, edX cloning, products) runs
        on the target instance.
        """
        contract_id = kwargs.pop("contract_id")
        output_path = kwargs.pop("output", None)

        if str(contract_id).isdecimal():
            contract = ContractPage.objects.filter(id=contract_id).first()
        else:
            contract = ContractPage.objects.filter(slug=contract_id).first()

        if not contract:
            msg = f"Contract '{contract_id}' not found."
            raise CommandError(msg)

        org = contract.organization
        course_ct = ContentType.objects.get(app_label="courses", model="course")
        contract_ct = ContentType.objects.get(app_label="b2b", model="contractpage")

        programs_data = []
        for program_item in (
            contract.contract_programs.order_by("sort_order")
            .select_related("program")
            .all()
        ):
            program = program_item.program

            course_reqs = (
                ProgramRequirement.objects.filter(
                    program=program,
                    node_type=ProgramRequirementNodeType.COURSE,
                    course__isnull=False,
                )
                .select_related("course")
                .order_by("path")
                .all()
            )

            courses_data = []
            for req in course_reqs:
                course = req.course

                designated = (
                    CourseRun.all_objects.filter(course=course)
                    .filter(Q(is_source_run=True) | Q(run_tag="SOURCE"))
                    .prefetch_related("enrollment_modes")
                    .order_by("id")
                )

                if designated.exists():
                    source_runs_data = [_serialize_run(run) for run in designated]
                else:
                    # Older contracts never set is_source_run or run_tag="SOURCE".
                    # Fall back to the most recent non-B2B run per variant combo,
                    # mirroring create_contract_run's require_designated_source_run=False
                    # behaviour.  Export with is_source_run=True so the import flags
                    # them correctly and create_contract_run can find them.
                    non_b2b = (
                        CourseRun.all_objects.filter(
                            course=course, b2b_contract__isnull=True
                        )
                        .exclude(Q(is_source_run=True) | Q(run_tag="SOURCE"))
                        .prefetch_related("enrollment_modes")
                        .order_by("-id")
                    )

                    # If the course has a default variant language, use it for
                    # runs that have NULL/empty language.  This ensures the
                    # exported run matches _get_source_runs_for_course variant
                    # filtering on the target instance.
                    default_sv = SupportedVariant.objects.filter(
                        content_type=course_ct,
                        object_id=course.id,
                        default_variant=True,
                    ).first()
                    default_lang = default_sv.language if default_sv else None

                    seen: set = set()
                    fallback = []
                    for run in non_b2b:
                        eff_lang = run.language or default_lang or ""
                        key = (
                            eff_lang,
                            run.variant_industry or "",
                            run.variant_length or "",
                        )
                        if key not in seen:
                            seen.add(key)
                            fallback.append((run, eff_lang))

                    source_runs_data = [
                        _serialize_run(
                            run,
                            force_is_source_run=True,
                            language_override=eff_lang if eff_lang else None,
                        )
                        for run, eff_lang in fallback
                    ]

                    if fallback:
                        self.stderr.write(
                            self.style.WARNING(
                                f"  Course {course.readable_id}: no designated source "
                                f"runs; using {len(fallback)} most-recent non-B2B "
                                "run(s) as fallback (will be flagged is_source_run=True on import)"
                            )
                        )
                    else:
                        self.stderr.write(
                            self.style.WARNING(
                                f"  Course {course.readable_id} has no source runs and "
                                "no non-B2B runs — contract runs cannot be recreated on import."
                            )
                        )

                courses_data.append(
                    {
                        "readable_id": course.readable_id,
                        "title": course.title,
                        "departments": [d.name for d in course.departments.all()],
                        "variant_options": _serialize_variant_options(
                            SupportedVariant.objects.filter(
                                content_type=course_ct, object_id=course.id
                            )
                        ),
                        "source_runs": source_runs_data,
                    }
                )

            programs_data.append(
                {
                    "readable_id": program.readable_id,
                    "title": program.title,
                    "sort_order": program_item.sort_order,
                    "departments": [d.name for d in program.departments.all()],
                    "courses": courses_data,
                }
            )

        payload = {
            "version": 1,
            "exported_at": now_in_utc().isoformat(),
            "source_contract_id": contract.id,
            "source_contract_slug": contract.slug,
            "organization": {
                "name": org.name,
                "org_key": org.org_key,
                "org_key_prefix": org.org_key_prefix,
                "sso_organization_id": (
                    str(org.sso_organization_id) if org.sso_organization_id else None
                ),
            },
            "contract": {
                "name": contract.name,
                "slug": contract.slug,
                "description": contract.description,
                "welcome_message": contract.welcome_message,
                "welcome_message_extra": contract.welcome_message_extra,
                "membership_type": contract.membership_type,
                "contract_start": _serialize_date(contract.contract_start),
                "contract_end": _serialize_date(contract.contract_end),
                "active": contract.active,
                "max_learners": contract.max_learners,
                "enrollment_fixed_price": (
                    str(contract.enrollment_fixed_price)
                    if contract.enrollment_fixed_price is not None
                    else None
                ),
                "google_sheet_target": contract.google_sheet_target,
                "google_sheet_target_tab": contract.google_sheet_target_tab,
                "variant_options": _serialize_variant_options(
                    SupportedVariant.objects.filter(
                        content_type=contract_ct, object_id=contract.id
                    )
                ),
            },
            "programs": programs_data,
        }

        output = json.dumps(payload, indent=2)

        if output_path:
            with open(output_path, "w") as f:  # noqa: PTH123
                f.write(output)
            self.stderr.write(
                self.style.SUCCESS(
                    f"Contract '{contract.slug}' exported to {output_path}"
                )
            )
        else:
            self.stdout.write(output)

    # ------------------------------------------------------------------ import

    def _ensure_cms_infrastructure(self):
        """Guarantee the CMS index pages and site exist before adding courseware."""
        from b2b.api import ensure_b2b_organization_index  # noqa: PLC0415
        from cms.api import (  # noqa: PLC0415
            ensure_home_page_and_site,
            ensure_product_index,
            ensure_program_product_index,
        )

        ensure_home_page_and_site()
        ensure_product_index()
        ensure_program_product_index()
        return ensure_b2b_organization_index()

    def _ensure_courseware_page(self, courseware):
        """Return the live CMS page for courseware, creating it if absent."""
        from cms.api import create_default_courseware_page  # noqa: PLC0415

        try:
            page = courseware.page
        except ObjectDoesNotExist:
            page = None

        if page is not None:
            if not page.live:
                page.live = True
                page.save_revision().publish()
            return page

        return create_default_courseware_page(courseware, live=True)

    def _import_organization(self, org_index, org_data):
        """Get or create the OrganizationPage from exported org data."""
        org = OrganizationPage.objects.filter(org_key=org_data["org_key"]).first()
        if org:
            self.stdout.write(f"  Organization exists: {org.org_key}")
            return org

        org = OrganizationPage(
            name=org_data["name"],
            org_key=org_data["org_key"],
            org_key_prefix=org_data.get("org_key_prefix", ""),
        )
        if org_data.get("sso_organization_id"):
            org.sso_organization_id = org_data["sso_organization_id"]
        org_index.add_child(instance=org)
        org.save()
        self.stdout.write(self.style.SUCCESS(f"  Created organization: {org.org_key}"))
        return org

    def _import_contract(self, org, contract_data, slug):
        """Get or create the ContractPage from exported contract data."""
        contract = ContractPage.objects.filter(slug=slug).first()
        if contract:
            self.stdout.write(f"  Contract exists: {slug}")
            return contract

        fixed_price = (
            Decimal(contract_data["enrollment_fixed_price"])
            if contract_data.get("enrollment_fixed_price")
            else None
        )
        contract = ContractPage(
            name=contract_data["name"],
            slug=slug,
            description=contract_data.get("description", ""),
            welcome_message=contract_data.get("welcome_message", ""),
            welcome_message_extra=contract_data.get("welcome_message_extra", ""),
            membership_type=contract_data["membership_type"],
            organization=org,
            contract_start=contract_data.get("contract_start"),
            contract_end=contract_data.get("contract_end"),
            active=contract_data.get("active", True),
            max_learners=contract_data.get("max_learners"),
            enrollment_fixed_price=fixed_price,
            google_sheet_target=contract_data.get("google_sheet_target") or "",
            google_sheet_target_tab=contract_data.get(
                "google_sheet_target_tab", "Sheet1"
            ),
        )
        org.add_child(instance=contract)
        contract.save()
        self.stdout.write(self.style.SUCCESS(f"  Created contract: {slug}"))
        return contract

    def _upsert_variant_options(self, obj, variants_data):
        """Create any SupportedVariant records on obj that don't already exist."""
        ct = ContentType.objects.get_for_model(obj.__class__)
        created = 0
        for vd in variants_data:
            _, was_created = SupportedVariant.objects.get_or_create(
                content_type=ct,
                object_id=obj.id,
                language=vd["language"],
                variant_industry=vd["variant_industry"],
                variant_length=vd["variant_length"],
                defaults={
                    "b2b_only": vd["b2b_only"],
                    "default_variant": vd["default_variant"],
                    "active": True,
                },
            )
            if was_created:
                created += 1
        return created

    def _import_source_runs(self, course, source_runs_data):
        """Get or create source runs from exported run data.

        When the exported data marks a run as is_source_run=True but the run
        already exists on this instance with is_source_run=False (the common
        case for older contracts that never set the flag), update just that
        field so create_contract_run can find the run.
        """
        created = 0
        for rd in source_runs_data:
            run, was_created = CourseRun.all_objects.get_or_create(
                courseware_id=rd["courseware_id"],
                defaults={
                    "course": course,
                    "title": rd["title"],
                    "run_tag": rd["run_tag"],
                    "is_source_run": rd["is_source_run"],
                    "is_primary_language": rd.get("is_primary_language", False),
                    "language": rd.get("language", ""),
                    "variant_industry": rd.get("variant_industry", ""),
                    "variant_length": rd.get("variant_length", ""),
                    "start_date": rd.get("start_date"),
                    "end_date": rd.get("end_date"),
                    "enrollment_start": rd.get("enrollment_start"),
                    "enrollment_end": rd.get("enrollment_end"),
                    "live": rd.get("live", True),
                    "is_self_paced": rd.get("is_self_paced", True),
                    "has_courseware_url": rd.get("has_courseware_url", False),
                },
            )
            if was_created:
                created += 1
            elif rd["is_source_run"] and not run.is_source_run:
                update_fields = ["is_source_run"]
                run.is_source_run = True
                # Sync language/variant fields from the export data.  The export
                # may have corrected NULL → "" and applied the course's default
                # variant language, so the run must match for
                # _get_source_runs_for_course variant filtering to succeed.
                for field in ("language", "variant_industry", "variant_length"):
                    exported_val = rd.get(field, "")
                    if getattr(run, field) != exported_val:
                        setattr(run, field, exported_val)
                        update_fields.append(field)
                run.save(update_fields=update_fields)

            for mode_slug in rd.get("enrollment_modes", []):
                mode, _ = EnrollmentMode.objects.get_or_create(mode_slug=mode_slug)
                run.enrollment_modes.add(mode)

        return created

    def _import_course(self, course_data):
        """Get or create a course with its page, departments, source runs, and variants."""
        course, was_created = Course.objects.get_or_create(
            readable_id=course_data["readable_id"],
            defaults={"title": course_data["title"], "live": True},
        )
        if was_created:
            self.stdout.write(
                self.style.SUCCESS(f"    Created course: {course_data['readable_id']}")
            )
        else:
            self.stdout.write(f"    Course exists: {course_data['readable_id']}")

        for dept_name in course_data.get("departments", []):
            dept, _ = Department.objects.get_or_create(name=dept_name)
            course.departments.add(dept)

        self._ensure_courseware_page(course)

        runs_created = self._import_source_runs(
            course, course_data.get("source_runs", [])
        )
        if runs_created:
            self.stdout.write(f"      Created {runs_created} source run(s)")
        elif course_data.get("source_runs"):
            self.stdout.write("      Source runs already exist")
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"      No source runs for {course_data['readable_id']} — "
                    "contract runs cannot be created for this course"
                )
            )

        variants_created = self._upsert_variant_options(
            course, course_data.get("variant_options", [])
        )
        if variants_created:
            self.stdout.write(f"      Created {variants_created} variant option(s)")

        return course

    def _import_program(self, prog_data):
        """Get or create a program with its page, departments, and courses."""
        program, was_created = Program.objects.get_or_create(
            readable_id=prog_data["readable_id"],
            defaults={"title": prog_data["title"], "live": True},
        )
        if was_created:
            self.stdout.write(
                self.style.SUCCESS(f"  Created program: {prog_data['readable_id']}")
            )
        else:
            self.stdout.write(f"  Program exists: {prog_data['readable_id']}")

        for dept_name in prog_data.get("departments", []):
            dept, _ = Department.objects.get_or_create(name=dept_name)
            program.departments.add(dept)

        self._ensure_courseware_page(program)

        # Track which courses are already required by this program so we don't
        # call add_requirement twice (it deletes+recreates the node, which is
        # harmless but noisy).
        existing_course_ids = set(
            ProgramRequirement.objects.filter(
                program=program,
                node_type=ProgramRequirementNodeType.COURSE,
                course__isnull=False,
            ).values_list("course_id", flat=True)
        )

        for course_data in prog_data.get("courses", []):
            course = self._import_course(course_data)
            if course.id not in existing_course_ids:
                program.add_requirement(course)
                existing_course_ids.add(course.id)

        return program

    def _run_import_transaction(self, data, slug_override, skip_runs):
        """All DB work for one import, executed inside an open transaction.

        Returns the ContractPage that was created or found.
        """
        self.stdout.write("\nStep 0: CMS infrastructure")
        org_index = self._ensure_cms_infrastructure()

        self.stdout.write("\nStep 1: Organization")
        org = self._import_organization(org_index, data["organization"])

        self.stdout.write("\nStep 2: Programs and courses")
        programs_with_order = []
        for prog_data in data["programs"]:
            program = self._import_program(prog_data)
            programs_with_order.append((program, prog_data["sort_order"]))

        self.stdout.write("\nStep 3: Contract")
        slug = slug_override or data["contract"]["slug"]
        contract = self._import_contract(org, data["contract"], slug)

        self.stdout.write("\nStep 4: Contract variant options")
        n = self._upsert_variant_options(
            contract, data["contract"].get("variant_options", [])
        )
        self.stdout.write(f"  {n} variant option(s) created")

        if skip_runs:
            self._link_programs_skip_runs(contract, programs_with_order)
        else:
            self._create_contract_runs(contract, programs_with_order)

        return contract

    def _link_programs_skip_runs(self, contract, programs_with_order):
        """Link programs to the contract without creating any contract runs."""
        self.stdout.write("\nStep 5: Linking programs (--skip-runs set)")
        for program, sort_order in programs_with_order:
            exists = ContractProgramItem.objects.filter(
                contract=contract, program=program
            ).exists()
            if not exists:
                ContractProgramItem(
                    contract=contract,
                    program=program,
                    sort_order=sort_order,
                ).save(skip_run_creation=True)
                self.stdout.write(f"  Linked {program.readable_id}")

    def _create_contract_runs(self, contract, programs_with_order):
        """Call add_program_courses for each program, generating contract runs."""
        self.stdout.write("\nStep 5: Contract runs")
        # Reload so cached_property fields see the variant records we just created.
        contract.refresh_from_db()
        filter_variants = list(contract.variant_options.all())
        total_created = 0
        total_no_source = 0

        for program, sort_order in programs_with_order:
            self.stdout.write(f"  Program: {program.readable_id}")
            try:
                created, no_source = contract.add_program_courses(
                    program,
                    order=sort_order,
                    skip_edx=True,
                    no_reruns=True,
                    filter_variants=filter_variants,
                )
            except SourceCourseIncompleteError as exc:
                self.stdout.write(
                    self.style.WARNING(f"    Skipped (no source run): {exc}")
                )
                # Still attach the program so the contract structure is complete.
                exists = ContractProgramItem.objects.filter(
                    contract=contract, program=program
                ).exists()
                if not exists:
                    ContractProgramItem(
                        contract=contract,
                        program=program,
                        sort_order=sort_order,
                    ).save(skip_run_creation=True)
                continue

            total_created += created
            total_no_source += no_source
            if no_source:
                self.stdout.write(
                    self.style.WARNING(
                        f"    {no_source} course(s) had no source run and were skipped"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"  Created {total_created} contract run(s), "
                f"{total_no_source} course(s) without source runs skipped"
            )
        )

    def handle_import(self, *args, **kwargs):  # noqa: ARG002
        """Import a contract from a JSON export payload.

        Recreates the organization, programs, courses, source runs, and variant
        options on the target instance, then calls create_contract_run for each
        course so that contract-specific runs are generated using the same
        machinery as production.  edX is never contacted during import.
        """
        input_path = kwargs.pop("input")
        dry_run = kwargs.pop("dry_run", True)
        slug_override = kwargs.pop("slug", None)
        skip_runs = kwargs.pop("skip_runs", False)

        if input_path == "-":
            data = json.load(sys.stdin)
        else:
            with open(input_path) as f:  # noqa: PTH123
                data = json.load(f)

        if data.get("version") != 1:
            msg = f"Unsupported export format version {data.get('version')!r}, expected 1."
            raise CommandError(msg)

        self.stdout.write(
            f"Importing contract '{data.get('source_contract_slug', '<unknown>')}' "
            f"(exported {data.get('exported_at', 'unknown date')})"
            + (" [DRY RUN]" if dry_run else "")
        )

        with transaction.atomic():
            contract = self._run_import_transaction(data, slug_override, skip_runs)
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        "\nDry run — rolling back. Pass --commit to apply changes."
                    )
                )
                transaction.set_rollback(True)
                return

        self.stdout.write(
            self.style.SUCCESS(
                f"\nImport complete. Contract slug: {contract.slug} (id={contract.id})"
            )
        )

    # ----------------------------------------------------------------- dispatch

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Handle the command."""
        subcommand = kwargs.pop("subcommand")
        if subcommand == "create":
            self.handle_create(**kwargs)
        elif subcommand == "modify":
            self.handle_modify(**kwargs)
        elif subcommand == "export":
            self.handle_export(**kwargs)
        elif subcommand == "import":
            self.handle_import(**kwargs)
        else:
            log.error("Unknown subcommand: %s", subcommand)
            return 1
        return 0
