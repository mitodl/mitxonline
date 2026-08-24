#!/usr/bin/env bash
set -eo pipefail

TMPDIR="$(mktemp -d)"
SPEC_FILE="${KEYCLOAK_OPENAPI_SPEC_FILE:-$TMPDIR/keycloak-openapi.yaml}"

if [ ! -s "$SPEC_FILE" ]; then
	mkdir -p "$(dirname "$SPEC_FILE")"
	curl -sSL -o "$SPEC_FILE" https://www.keycloak.org/docs-api/latest/rest-api/openapi.yaml
fi

uv run datamodel-codegen --output-model-type pydantic_v2.BaseModel --preset standard-py312-20260619 --output $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp --input "$SPEC_FILE" --input-file-type openapi --enable-version-header --enable-command-header

sed -i "s|$TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp|b2b/keycloak_admin_dataclasses.py|g" $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp
diff ./b2b/keycloak_admin_dataclasses.py $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp

# If we're here we know we've succeeded as a non-zero diff exit code aborts the script via `set -e`
echo "KC Admin Dataclasses up to date!"
exit 0
