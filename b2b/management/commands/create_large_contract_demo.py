"""
Seed a large B2B demo dataset entirely within MITx Online (no edX calls).

Creates 20 courses, each supporting 15 variants (language en/fr/ja, crossed
with the "Full" length variant across all industries and the "Short" length
variant for the default industry), plus one source CourseRun per variant.
Those courses are wired into a single "all required, no electives" program,
which is then attached to a bespoke "large contract" organization/contract,
generating one contract CourseRun (and Product) per course variant.
"""

import logging
from datetime import timedelta

from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from django.db import transaction
from mitol.common.utils import now_in_utc

from b2b.api import ensure_b2b_organization_index
from b2b.constants import CONTRACT_MEMBERSHIP_MANAGED
from b2b.models import ContractPage, OrganizationPage
from courses.constants import UAI_COURSEWARE_ID_PREFIX
from courses.models import Course, CourseRun, EnrollmentMode, Program
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from variants.models import SupportedVariant

log = logging.getLogger(__name__)

COURSE_COUNT = 20
CATALOG_ORG = "LCDemo"

# (variant_length, variant_industry) combos applied to every language. The
# "Full"/"" length is crossed with every industry; "Short" only exists for
# the original (non-industry-specific) content.
LENGTH_INDUSTRY_COMBOS = [
    ("", ""),
    ("S", ""),
    ("", "E"),
    ("", "F"),
    ("", "HC"),
]
LANGUAGES = ["en", "fr", "ja"]

ORG_KEY = "LARGECONTRACT"
ORG_NAME = "Large Contract Co."
CONTRACT_NAME = "Large Contract Demo Contract"
PROGRAM_READABLE_ID = "program-v1:LCDemo+LargeContractProgram"
PROGRAM_TITLE = "Large Contract Demo Program"


def _iter_variant_combos():
    """Yield (language, variant_length, variant_industry, is_default) tuples."""

    for language in LANGUAGES:
        for variant_length, variant_industry in LENGTH_INDUSTRY_COMBOS:
            is_default = (
                language == "en" and not variant_length and not variant_industry
            )
            yield language, variant_length, variant_industry, is_default


class Command(BaseCommand):
    """Seed a large B2B demo dataset (courses, program, org, contract, runs)."""

    help = (
        "Create 20 courses (15 language/length/industry variants each with "
        "source runs), a single required-courses program, and a bespoke "
        "'large contract' org/contract with the program attached and contract "
        "runs generated. Does not talk to edX - MITx Online objects only."
    )

    def handle(self, *_args, **_kwargs):
        """Build the demo dataset."""

        with transaction.atomic():
            audit_mode, _ = EnrollmentMode.objects.get_or_create(
                mode_slug=EDX_ENROLLMENT_AUDIT_MODE
            )
            verified_mode, _ = EnrollmentMode.objects.get_or_create(
                mode_slug=EDX_ENROLLMENT_VERIFIED_MODE
            )

            courses = self._create_courses(audit_mode, verified_mode)
            program = self._create_program(courses)
            contract = self._create_org_and_contract()

            self.stdout.write(
                "Attaching program to contract and creating contract runs..."
            )
            contract.add_program_courses(program, skip_edx=True)

        run_count = contract.get_course_runs().count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {len(courses)} courses, program {program.readable_id!r}, "
                f"contract {contract.name!r} (org {contract.organization.org_key!r}) "
                f"with {run_count} contract course runs."
            )
        )

    def _create_courses(self, audit_mode, verified_mode):
        """Create the demo courses, each with 15 variants and source runs."""

        course_ct = ContentType.objects.get_for_model(Course)
        start_date = now_in_utc() - timedelta(days=7)
        end_date = now_in_utc() + timedelta(days=180)
        enrollment_end = now_in_utc() + timedelta(days=150)

        courses = []
        for i in range(1, COURSE_COUNT + 1):
            course_num = f"C{i:03d}"
            readable_id = f"course-v1:{CATALOG_ORG}+{course_num}"
            course, created = Course.objects.get_or_create(
                readable_id=readable_id,
                defaults={
                    "title": f"Large Contract Demo Course {i:02d}",
                    "live": True,
                },
            )
            courses.append(course)

            if not created:
                self.stdout.write(f"Course {readable_id} already exists, skipping.")
                continue

            for idx, (
                language,
                variant_length,
                variant_industry,
                is_default,
            ) in enumerate(_iter_variant_combos(), start=1):
                SupportedVariant.objects.create(
                    content_type=course_ct,
                    object_id=course.id,
                    language=language,
                    variant_length=variant_length,
                    variant_industry=variant_industry,
                    active=True,
                    b2b_only=False,
                    default_variant=is_default,
                )

                run = CourseRun.objects.create(
                    course=course,
                    title=f"{course.title} (source, {language}/{variant_length or 'Full'}/{variant_industry or 'Original'})",
                    courseware_id=f"{readable_id}+SRC{idx:02d}",
                    run_tag="SOURCE",
                    is_source_run=True,
                    is_primary_language=is_default,
                    language=language,
                    variant_length=variant_length,
                    variant_industry=variant_industry,
                    live=True,
                    is_self_paced=True,
                    has_courseware_url=False,
                    start_date=start_date,
                    end_date=end_date,
                    enrollment_start=start_date,
                    enrollment_end=enrollment_end,
                    certificate_available_date=end_date,
                )
                run.enrollment_modes.add(audit_mode, verified_mode)

            self.stdout.write(f"Created course {readable_id} with 15 variants/runs.")

        return courses

    def _create_program(self, courses):
        """Create the program and add every course as a (non-elective) requirement."""

        program, created = Program.objects.get_or_create(
            readable_id=PROGRAM_READABLE_ID,
            defaults={"title": PROGRAM_TITLE, "live": True},
        )

        for course in courses:
            program.add_requirement(course)

        if created:
            self.stdout.write(f"Created program {PROGRAM_READABLE_ID}.")
        else:
            self.stdout.write(f"Program {PROGRAM_READABLE_ID} already exists, reused.")

        return program

    def _create_org_and_contract(self):
        """Create the bespoke large-contract organization and contract."""

        org = OrganizationPage.objects.filter(org_key=ORG_KEY).first()
        if not org:
            org_index = ensure_b2b_organization_index()
            org = OrganizationPage(
                name=ORG_NAME,
                org_key=ORG_KEY,
                org_key_prefix=UAI_COURSEWARE_ID_PREFIX,
                live=True,
                description="Demo organization for large-contract testing.",
            )
            org_index.add_child(instance=org)
            org.refresh_from_db()
            self.stdout.write(f"Created organization {ORG_NAME} ({ORG_KEY}).")

        contract = ContractPage.objects.filter(
            organization=org, name=CONTRACT_NAME
        ).first()
        if not contract:
            today = now_in_utc().date()
            contract = ContractPage(
                name=CONTRACT_NAME,
                organization=org,
                membership_type=CONTRACT_MEMBERSHIP_MANAGED,
                active=True,
                contract_start=today,
                contract_end=today + timedelta(days=365),
                live=True,
                description="Demo contract for large-contract testing.",
            )
            org.add_child(instance=contract)
            contract.refresh_from_db()
            self.stdout.write(f"Created contract {CONTRACT_NAME}.")

        if not contract.variant_options.exists():
            contract_ct = ContentType.objects.get_for_model(ContractPage)
            for (
                language,
                variant_length,
                variant_industry,
                is_default,
            ) in _iter_variant_combos():
                SupportedVariant.objects.create(
                    content_type=contract_ct,
                    object_id=contract.id,
                    language=language,
                    variant_length=variant_length,
                    variant_industry=variant_industry,
                    active=True,
                    b2b_only=False,
                    default_variant=is_default,
                )
            self.stdout.write("Added variant options to the contract.")

        return contract
