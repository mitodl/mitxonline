#!/usr/bin/env bash
set -eo pipefail

TMPDIR="$(mktemp -d)"

uv run datamodel-codegen --output-model-type pydantic_v2.BaseModel --preset standard-py312-20260619 --output $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp --url https://www.keycloak.org/docs-api/latest/rest-api/openapi.yaml --enable-version-header --enable-command-header

sed -i '' "s|$TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp|b2b/keycloak_admin_dataclasses.py|g" $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp
diff ./b2b/keycloak_admin_dataclasses.py $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp

# If we're here we know we've succeeded as a non-zero diff exit code aborts the script via `set -e`
echo "KC Admin Dataclasses up to date!"
exit 0
