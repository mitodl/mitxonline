import pytest

from cms.factories import ProgramPageFactory


@pytest.mark.django_db
def test_anonymous_program_page_listing_filters_by_learn_catalog_flag(api_client):
    included_page = ProgramPageFactory.create(
        live=True,
        include_in_learn_catalog=True,
        program__b2b_only=False,
    )
    excluded_page = ProgramPageFactory.create(
        live=True,
        include_in_learn_catalog=False,
        program__b2b_only=False,
    )

    response = api_client.get("/api/v2/pages/", {"type": "cms.programpage"})

    assert response.status_code == 200
    returned_page_ids = {item["id"] for item in response.json()["items"]}
    assert included_page.id in returned_page_ids
    assert excluded_page.id not in returned_page_ids


@pytest.mark.django_db
def test_anonymous_program_page_listing_filters_out_b2b_pages(api_client):
    included_page = ProgramPageFactory.create(
        live=True,
        include_in_learn_catalog=True,
        program__b2b_only=False,
    )
    excluded_page = ProgramPageFactory.create(
        live=True,
        include_in_learn_catalog=True,
        program__b2b_only=True,
    )

    response = api_client.get("/api/v2/pages/", {"type": "cms.programpage"})

    assert response.status_code == 200
    returned_page_ids = {item["id"] for item in response.json()["items"]}
    assert included_page.id in returned_page_ids
    assert excluded_page.id not in returned_page_ids
