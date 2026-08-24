#!/usr/bin/env bash
set -eo pipefail

TMPDIR="$(mktemp -d)"
SPEC_FILE="${KEYCLOAK_OPENAPI_SPEC_FILE:-$TMPDIR/keycloak-openapi.yaml}"

if [ -s "$SPEC_FILE" ]; then
	echo "Found cached Keycloak OpenAPI spec at $SPEC_FILE, skipping download"
else
	echo "No cached Keycloak OpenAPI spec found at $SPEC_FILE, downloading"
	mkdir -p "$(dirname "$SPEC_FILE")"
	curl -sSL -o "$SPEC_FILE" https://www.keycloak.org/docs-api/latest/rest-api/openapi.yaml
fi

uv run datamodel-codegen --output-model-type pydantic_v2.BaseModel --preset standard-py312-20260619 --output $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp --input "$SPEC_FILE" --input-file-type openapi --enable-version-header --enable-command-header

# Skip the first 4 header lines (filename/version/command) since those legitimately
# differ between the `--url`-based command used to actually regenerate the committed
# file and the `--input`-based command used here to check against a cached spec.
diff <(tail -n +5 ./b2b/keycloak_admin_dataclasses.py) <(tail -n +4 $TMPDIR/b2b/keycloak_admin_dataclasses.py.tmp)

# If we're here we know we've succeeded as a non-zero diff exit code aborts the script via `set -e`
echo "KC Admin Dataclasses up to date!"
exit 0
