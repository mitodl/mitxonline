"""Tests for B2B serializers (v0)."""

import re

import pytest

from b2b.factories import ContractPageFactory
from b2b.serializers.v0 import ContractPageSerializer


@pytest.mark.django_db
def test_contract_page_serializer_expands_embeds():
    """Test that welcome_message_extra expands embed tags and preserves HTML."""
    contract = ContractPageFactory.create(
        welcome_message_extra=(
            "<p>Hello, world</p>"
            '<embed embedtype="media" url="https://www.youtube.com/watch?v=_AXZSRtsASE&amp;pp=ygUSZGltaXRyaXMgYmVydHNpbWFz"/>'
        )
    )

    serializer = ContractPageSerializer(contract)
    result = serializer.data["welcome_message_extra"]
    pattern = (
        r"<p>Hello, world</p><div>\s*"
        r'<iframe\s+[^>]*src="https://www\.youtube\.com/embed/_AXZSRtsASE\?feature=oembed"[^>]*>'
        r"</iframe>\s*"
        r"</div>"
    )
    assert re.match(pattern, result, re.DOTALL)
