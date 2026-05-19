"""Create HubSpot custom object schemas for certificate syncing."""

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from mitol.hubspot_api.api import HubspotApi, HubspotObjectType

from hubspot_sync.api import CERTIFICATE_CUSTOM_OBJECT_SCHEMAS
from hubspot_sync.rate_limiter import wait_for_hubspot_rate_limit


class Command(BaseCommand):
    """Create or verify certificate custom object schemas in HubSpot."""

    help = (
        "Create HubSpot custom object schemas for course/program certificates and "
        "print objectTypeId and contact association type IDs."
    )

    def handle(self, *args, **options):  # noqa: ARG002
        token = settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN
        if not token:
            raise CommandError("MITOL_HUBSPOT_API_PRIVATE_TOKEN is not configured")

        hubspot_client = HubspotApi(access_token=token)

        wait_for_hubspot_rate_limit()
        existing_schemas = hubspot_client.crm.schemas.core_api.get_all()
        existing_by_name = {
            schema.name: schema for schema in getattr(existing_schemas, "results", [])
        }

        created_or_existing = {}

        for schema_name, schema_payload in CERTIFICATE_CUSTOM_OBJECT_SCHEMAS.items():
            if schema_name in existing_by_name:
                schema = existing_by_name[schema_name]
                self.stdout.write(
                    self.style.WARNING(
                        f"Schema {schema_name} already exists (objectTypeId={schema.object_type_id})"
                    )
                )
                created_or_existing[schema_name] = schema
                continue

            wait_for_hubspot_rate_limit()
            schema = hubspot_client.crm.schemas.core_api.create(
                object_schema=schema_payload
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"Created schema {schema_name} (objectTypeId={schema.object_type_id})"
                )
            )
            created_or_existing[schema_name] = schema

        self.stdout.write("\nCertificate schema details:\n")
        env_output = []

        for schema_name, schema in created_or_existing.items():
            object_type_id = schema.object_type_id

            wait_for_hubspot_rate_limit()
            assoc_types = hubspot_client.crm.associations.v4.definition_api.get_all(
                from_object_type=object_type_id,
                to_object_type=HubspotObjectType.CONTACTS.value,
            )
            assoc_type_id = None
            if getattr(assoc_types, "results", None):
                assoc_type_id = assoc_types.results[0].type_id

            self.stdout.write(f"- {schema_name}")
            self.stdout.write(f"  objectTypeId: {object_type_id}")
            self.stdout.write(f"  contact association typeId: {assoc_type_id}")

            if schema_name == "course_run_certificate":
                env_output.extend(
                    [
                        f"HUBSPOT_COURSE_RUN_CERTIFICATE_OBJECT_TYPE={schema_name}",
                        "HUBSPOT_COURSE_RUN_CERTIFICATE_ASSOCIATION_TYPE_ID="
                        f"{assoc_type_id}",
                    ]
                )
            elif schema_name == "program_certificate":
                env_output.extend(
                    [
                        f"HUBSPOT_PROGRAM_CERTIFICATE_OBJECT_TYPE={schema_name}",
                        "HUBSPOT_PROGRAM_CERTIFICATE_ASSOCIATION_TYPE_ID="
                        f"{assoc_type_id}",
                    ]
                )

        self.stdout.write("\nAdd/update these environment settings:\n")
        for env_line in env_output:
            self.stdout.write(env_line)
