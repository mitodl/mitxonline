"""Quick-add a new B2B contract."""

import logging

from django.core.management import BaseCommand, CommandError
from django.db.models import Q
from django.utils.text import slugify

from b2b.constants import (
    CONTRACT_MEMBERSHIP_CODE,
)
from b2b.models import (
    ContractPage,
    OrganizationIndexPage,
    OrganizationPage,
)
from courses.api import resolve_courseware_object_from_id
from courses.models import (
    Course,
    CourseRun,
    Program,
)

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Quick-add a new B2B contract."""

    help = "Quick-add a new B2B contract. Creates a new org and contract, and adds the specified courseware to it. The created contract will be code-managed with a seat limit. Courseware can either be a program or course, or an existing course run. If the course run exists and is a source run, a new contract run will be created; if it exists, it will be added to the contract."

    def _validate_org_and_contract(self, **kwargs):
        """Validate the org and contract parameters."""

        org_name = kwargs.get("org")
        org_key = kwargs.get("org_key")
        contract_name = kwargs.get("contract_name")

        if not contract_name:
            msg = "Contract name not provided."
            raise CommandError(msg)

        contract_slug = slugify(contract_name)

        if not org_name:
            msg = "Organization name not provided."
            raise CommandError(msg)

        if not org_key:
            msg = "Organization key not provided."
            raise CommandError(msg)

        if OrganizationPage.objects.filter(
            Q(name=org_name) | Q(org_key=org_key)
        ).exists():
            msg = f"Organization name {org_name} or key {org_key} exist already."
            raise CommandError(msg)

        if ContractPage.objects.filter(
            Q(name=contract_name) | Q(slug=contract_slug)
        ).exists():
            msg = f"Contract name {contract_name} or slug {contract_slug}"
            raise CommandError(msg)

        return (org_name, org_key, contract_name, contract_slug)

    def _validate_courseware(self, coursewares):
        """Validate the specified courseware and sort resulting objects into buckets."""

        if len(coursewares) == 0:
            msg = "No courseware specified."
            raise CommandError(msg)

        programs = []
        courses = []
        courseruns = []

        for courseware in coursewares:
            courseware_obj = resolve_courseware_object_from_id(courseware)
            if not courseware_obj:
                log.warning("Courseware %s not found.", courseware)
            elif isinstance(courseware_obj, Program):
                programs.append(courseware_obj)
            elif isinstance(courseware_obj, Course):
                courses.append(courseware_obj)
            elif isinstance(courseware_obj, CourseRun):
                courseruns.append(courseware_obj)

        return (programs, courses, courseruns)

    def add_arguments(self, parser):
        """Add command line arguments."""

        parser.add_argument(
            "contract_name",
            type=str,
            help="The name of the contract.",
        )
        parser.add_argument(
            "--org",
            type=str,
            help="The name of the organization.",
        )
        parser.add_argument(
            "--org-key",
            type=str,
            help="The org key to use for the new organization.",
        )
        parser.add_argument(
            "--max-learners",
            type=int,
            help="The maximum number of learners for this contract.",
            default=None,
        )
        parser.add_argument(
            "--courseware",
            action="append",
            help="The courseware(s) to add (program, course, or course run).",
        )

        return super().add_arguments(parser)

    def handle(self, *args, **kwargs):  # noqa: ARG002
        """Create the org and contract and add courseware to it."""

        max_learners = kwargs.get("max_learners")

        (org_name, org_key, contract_name, contract_slug) = (
            self._validate_org_and_contract(**kwargs)
        )

        programs, courses, courseruns = self._validate_courseware(
            kwargs.get("courseware", [])
        )

        parent = OrganizationIndexPage.objects.first()
        org = OrganizationPage(name=org_name, org_key=org_key)
        parent.add_child(instance=org)
        org.save()
        parent.save()
        org.refresh_from_db()
        self.stdout.write(f"Created organization '{org_name}'")

        contract = ContractPage(
            name=contract_name,
            slug=contract_slug,
            membership_type=CONTRACT_MEMBERSHIP_CODE,
            organization=org,
            max_learners=max_learners,
        )
        org.add_child(instance=contract)
        contract.save()
        self.stdout.write(
            f"Created contract '{contract_name}' for organization '{org_name}'"
        )
