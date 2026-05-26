"""Create HubSpot custom object schemas for certificate syncing."""

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from hubspot.crm.objects import ApiException
from mitol.hubspot_api.api import HubspotApi, HubspotObjectType

from hubspot_sync.api import CERTIFICATE_CUSTOM_OBJECT_SCHEMAS
from hubspot_sync.rate_limiter import wait_for_hubspot_rate_limit


class Command(BaseCommand):
    """Create or verify certificate custom object schemas in HubSpot."""

    help = (
        "Create HubSpot custom object schemas for course/program certificates and "
        "print objectTypeId and contact association type IDs."
    )

    def _get_hubspot_client(self) -> HubspotApi:
        token = settings.MITOL_HUBSPOT_API_PRIVATE_TOKEN
        if not token:
            error_message = "MITOL_HUBSPOT_API_PRIVATE_TOKEN is not configured"
            raise CommandError(error_message)

        return HubspotApi(access_token=token)

    def _collect_existing_schemas(self, hubspot_client: HubspotApi) -> dict:
        wait_for_hubspot_rate_limit()
        existing_schemas = hubspot_client.crm.schemas.core_api.get_all()
        return {
            schema.name: schema for schema in getattr(existing_schemas, "results", [])
        }

    def _create_or_get_schemas(
        self, hubspot_client: HubspotApi, existing_by_name: dict
    ) -> dict:
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
            payload_with_name = {"name": schema_name, **schema_payload}
            try:
                schema = hubspot_client.crm.schemas.core_api.create(payload_with_name)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created schema {schema_name} (objectTypeId={schema.object_type_id})"
                    )
                )
                created_or_existing[schema_name] = schema
            except ApiException as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"Failed to create schema {schema_name}: {exc}"
                    )
                )
                raise

        return created_or_existing

    def _get_contact_assoc_type_id(
        self, hubspot_client: HubspotApi, schema_name: str, object_type_id: str
    ) -> int | None:
        try:
            wait_for_hubspot_rate_limit()
            assoc_types = hubspot_client.crm.associations.v4.definition_api.get_all(
                from_object_type=object_type_id,
                to_object_type=HubspotObjectType.CONTACTS.value,
            )
            if getattr(assoc_types, "results", None):
                return assoc_types.results[0].type_id
        except ApiException as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"Could not fetch association type ID for {schema_name}: {exc}"
                )
            )
        return None

    @staticmethod
    def _build_env_output(schema_name: str, assoc_type_id: int | None) -> list[str]:
        env_output = []
        if schema_name == "course_run_certificate":
            env_output.append(
                "HUBSPOT_COURSE_RUN_CERTIFICATE_OBJECT_TYPE=course_run_certificate"
            )
            if assoc_type_id:
                env_output.append(
                    f"HUBSPOT_COURSE_RUN_CERTIFICATE_ASSOCIATION_TYPE_ID={assoc_type_id}"
                )
        elif schema_name == "program_certificate":
            env_output.append(
                "HUBSPOT_PROGRAM_CERTIFICATE_OBJECT_TYPE=program_certificate"
            )
            if assoc_type_id:
                env_output.append(
                    f"HUBSPOT_PROGRAM_CERTIFICATE_ASSOCIATION_TYPE_ID={assoc_type_id}"
                )
        return env_output

    def handle(self, *_args, **_options):
        """Create missing certificate schemas and print related environment settings."""
        hubspot_client = self._get_hubspot_client()
        existing_by_name = self._collect_existing_schemas(hubspot_client)
        created_or_existing = self._create_or_get_schemas(
            hubspot_client, existing_by_name
        )

        self.stdout.write("\nCertificate schema details:\n")
        env_output = []

        for schema_name, schema in created_or_existing.items():
            object_type_id = schema.object_type_id

            assoc_type_id = self._get_contact_assoc_type_id(
                hubspot_client,
                schema_name,
                object_type_id,
            )

            self.stdout.write(f"- {schema_name}")
            self.stdout.write(f"  objectTypeId: {object_type_id}")
            if assoc_type_id:
                self.stdout.write(f"  contact association typeId: {assoc_type_id}")
            else:
                self.stdout.write(
                    "  contact association typeId: (will need to be set manually or auto-created on first sync)"
                )

            env_output.extend(self._build_env_output(schema_name, assoc_type_id))

        self.stdout.write("\nAdd/update these environment settings:\n")
        for env_line in env_output:
            self.stdout.write(env_line)
