"""Tests for B2B serializers (v0)."""

import json
from pathlib import Path

import pytest

from b2b.factories import ContractPageFactory
from b2b.serializers.v0 import ContractPageSerializer


@pytest.mark.django_db
def test_contract_page_serializer_expands_embeds(mocked_responses):
    """Test that welcome_message_extra expands embed tags and preserves HTML."""
    oembed = json.loads(
        Path("b2b/serializers/v0/data/youtube_oembed_response.json").read_text("utf-8")
    )
    mocked_responses.get("https://www.youtube.com/oembed", json=oembed)

    contract = ContractPageFactory.create(
        welcome_message_extra=(
            "<p>Hello, world</p>"
            '<embed embedtype="media" url="https://www.youtube.com/watch?v=_AXZSRtsASE&amp;pp=ygUSZGltaXRyaXMgYmVydHNpbWFz"/>'
        )
    )

    response = ContractPageSerializer(contract).data
    assert (
        response["welcome_message_extra"]
        == f"<p>Hello, world</p><div>\n    {oembed['html']}\n</div>\n"
    )
