"""Tests for B2B API functions."""

from decimal import Decimal
from zoneinfo import ZoneInfo

import faker
import pytest
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from mitol.common.utils import now_in_utc
from opaque_keys.edx.keys import CourseKey

from b2b import factories
from b2b.api import (
    _handle_extra_enrollment_codes,
    create_b2b_enrollment,
    create_contract_run,
    ensure_contract_run_pricing,
    ensure_contract_run_products,
    ensure_enrollment_codes_exist,
    get_active_contracts_from_basket_items,
    get_contract_products_with_bad_pricing,
    get_contract_runs_without_products,
    import_and_create_contract_run,
    process_add_org_membership,
    process_remove_org_membership,
    reconcile_keycloak_orgs,
    reconcile_single_keycloak_org,
    reconcile_user_orgs,
    validate_basket_for_b2b_purchase,
)
from b2b.constants import (
    B2B_RUN_TAG_FORMAT,
    CONTRACT_MEMBERSHIP_NONSSO,
    CONTRACT_MEMBERSHIP_SSO,
)
from b2b.exceptions import SourceCourseIncompleteError, TargetCourseRunExistsError
from b2b.factories import ContractPageFactory, OrganizationPageFactory
from b2b.models import OrganizationIndexPage, OrganizationPage, UserOrganization
from courses.constants import UAI_COURSEWARE_ID_PREFIX
from courses.factories import (
    CourseFactory,
    CourseRunEnrollmentFactory,
    CourseRunFactory,
    DepartmentFactory,
)
from courses.models import CourseRunEnrollment
from ecommerce.api_test import create_basket
from ecommerce.constants import REDEMPTION_TYPE_ONE_TIME, REDEMPTION_TYPE_UNLIMITED
from ecommerce.factories import (
    BasketFactory,
    BasketItemFactory,
    OneTimeDiscountFactory,
    ProductFactory,
    UnlimitedUseDiscountFactory,
)
from ecommerce.models import Basket, BasketDiscount, DiscountProduct
from main.constants import (
    USER_MSG_TYPE_B2B_DISALLOWED,
    USER_MSG_TYPE_B2B_ENROLL_SUCCESS,
    USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT,
    USER_MSG_TYPE_B2B_ERROR_NO_PRODUCT,
    USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT,
)
from main.utils import date_to_datetime
from openedx.constants import EDX_ENROLLMENT_VERIFIED_MODE
from users.factories import UserFactory

FAKE = faker.Faker()
pytestmark = [
    pytest.mark.django_db,
]


@pytest.fixture
def mocked_b2b_org_attach(mocker):
    """Mock the org attachment call."""

    return mocker.patch("b2b.api.add_user_org_membership", return_value=True)


@pytest.mark.parametrize(
    (
        "has_start",
        "has_end",
    ),
    [
        (True, True),
        (True, False),
        (False, True),
        (False, False),
    ],
)
def test_create_single_course_run(mocker, contract_ready_course, has_start, has_end):
    """Test that a single course run is created correctly for a contract."""

    now_time = now_in_utc()
    mocker.patch("b2b.api.now_in_utc", return_value=now_time)
    mocker.patch("openedx.tasks.clone_courserun.delay")

    contract = factories.ContractPageFactory(
        contract_start=FAKE.past_datetime(tzinfo=ZoneInfo(settings.TIME_ZONE))
        if has_start
        else None,
        contract_end=FAKE.future_datetime(tzinfo=ZoneInfo(settings.TIME_ZONE))
        if has_end
        else None,
    )
    (source_course, _) = contract_ready_course
    run, product = create_contract_run(contract, source_course)

    assert run.course == source_course
    assert run.run_tag == B2B_RUN_TAG_FORMAT.format(
        year=now_time.year, contract_id=contract.id
    )
    assert run.b2b_contract == contract

    if has_start:
        assertable_start = date_to_datetime(contract.contract_start, settings.TIME_ZONE)
    else:
        assertable_start = now_time
    assert run.start_date == assertable_start
    assert run.enrollment_start == assertable_start
    assert run.certificate_available_date == assertable_start

    if has_end:
        assert run.end_date == date_to_datetime(
            contract.contract_end, settings.TIME_ZONE
        )
        assert run.enrollment_end == date_to_datetime(
            contract.contract_end, settings.TIME_ZONE
        )
    else:
        assert run.end_date is None
        assert run.enrollment_end is None

    assert product.purchasable_object == run


@pytest.mark.parametrize(
    (
        "run_contract",
        "apply_code",
    ),
    [
        (False, False),
        (False, True),
        (True, False),
        (True, True),
    ],
)
def test_b2b_basket_validation(user, run_contract, apply_code):
    """
    Test that a basket is validated correctly for B2B contracts.

    Basically, if the user is adding a product that links to a course run that
    is also linked to a contract, we need to have also applied the discount code
    that matches the product, or we shouldn't be allowed to buy it.

    The truth table for this should be:

    | run_contract | apply_code | result |
    |--------------|------------|--------|
    | False        | False      | True   |
    | False        | True       | True   |
    | True         | False      | False  |
    | True         | True       | True  |
    """

    product = ProductFactory.create()
    discount = UnlimitedUseDiscountFactory.create()
    discount_product = DiscountProduct.objects.create(
        discount=discount, product=product
    )
    discount_product.save()
    discount.products.add(discount_product)

    if run_contract:
        contract = factories.ContractPageFactory.create()

        product.purchasable_object.b2b_contract = contract
        product.purchasable_object.save()
        product.refresh_from_db()

    basket = create_basket(user, [product])

    if apply_code:
        redemption = BasketDiscount(
            redemption_date=now_in_utc(),
            redeemed_by=user,
            redeemed_discount=discount,
            redeemed_basket=basket,
        )

        redemption.save()
        basket.refresh_from_db()

    active_contracts = get_active_contracts_from_basket_items(basket)
    check_result = validate_basket_for_b2b_purchase(basket, active_contracts)

    if run_contract and not apply_code:
        # User is trying to buy something that's linked to a contract but hasn't
        # applied the code, so this should be false.
        assert check_result is False
    else:
        assert check_result is True


@pytest.mark.parametrize(
    (
        "is_sso",
        "has_price",
        "has_learner_cap",
        "update_change_price",
        "update_no_price",
        "update_sso",
    ),
    [
        (False, False, False, False, False, False),
        (False, False, True, False, False, False),
        (False, True, False, False, False, False),
        (False, True, True, False, False, False),
        (True, False, False, False, False, False),
        (True, False, True, False, False, False),
        (True, True, False, False, False, False),
        (True, True, True, False, False, False),
        (False, False, False, True, False, False),
        (False, False, True, True, False, False),
        (False, True, False, True, False, False),
        (False, True, True, True, False, False),
        (False, False, False, False, True, False),
        (False, False, True, False, True, False),
        (True, False, False, True, False, False),
        (True, False, True, True, False, False),
        (True, True, False, True, False, False),
        (True, True, True, True, False, False),
        (True, True, False, False, False, True),
        (True, True, True, False, False, True),
        (False, False, False, False, False, True),
        (False, False, True, False, False, True),
        (False, True, False, False, False, True),
        (False, True, True, False, False, True),
    ],
)
def test_ensure_enrollment_codes(  # noqa: PLR0913
    mocker,
    contract_ready_course,
    is_sso,
    has_price,
    has_learner_cap,
    update_change_price,
    update_no_price,
    update_sso,
):
    """
    Test that the enrollment codes are created correctly for a contract.

    This tests scenarios where contract data changes, which should also change
    the discounts that are created.

    These are the scenarios in order (run each with a learner cap and without):
    - Just create fixed-price $0 discounts for non-sso contract
    - Just create discounts for contract price for non-sso contract
    - Just create fixed-price $0 discounts for sso contract
    - Just create discounts for contract price for sso contract
    - fixed-price $0 discount to random new price
    - priced discount to new price discount
    - fixed-price $0 discount to no price - this should be a no-op
    - sso fixed-price $0 discount to random new price
    - sso price discount to new price discount
    - sso price discount to non-sso - should also no-op
    - non-sso fixed-price $0 discount to sso - should remove all discounts
    - non-sso price to sso - should no-op
    """

    mocker.patch("openedx.tasks.clone_courserun.delay")
    mocked_ensure_call = mocker.patch("b2b.tasks.queue_enrollment_code_check.delay")
    max_learners = FAKE.random_int(min=1, max=15) if has_learner_cap else None
    price = FAKE.random_int(min=0, max=100) if has_price else None
    assert_price = price if price else Decimal(0)

    contract = factories.ContractPageFactory(
        integration_type=CONTRACT_MEMBERSHIP_SSO
        if is_sso
        else CONTRACT_MEMBERSHIP_NONSSO,
        membership_type=CONTRACT_MEMBERSHIP_SSO
        if is_sso
        else CONTRACT_MEMBERSHIP_NONSSO,
        enrollment_fixed_price=price,
        max_learners=max_learners,
    )
    (course, _) = contract_ready_course

    assert contract.get_discounts().count() == 0

    _, product = create_contract_run(contract, course)
    assert mocked_ensure_call.called

    ensure_enrollment_codes_exist(contract)

    if is_sso and not has_price:
        assert contract.get_discounts().count() == 0
    else:
        assert (
            contract.get_discounts().count() == max_learners if has_learner_cap else 1
        )

    for code in contract.get_discounts():
        assert code.amount == assert_price
        assert code.products.filter(product=product).exists()
        if has_learner_cap:
            assert code.redemption_type == REDEMPTION_TYPE_ONE_TIME
        else:
            assert code.redemption_type == REDEMPTION_TYPE_UNLIMITED

    # If the contract is updated later, the codes should also be updated accordingly.
    # Specifically:
    # - If we've changed the price, the discounts should also change amounts.
    # - If we've removed the price, the discounts should be set to 0.
    # - If we've set the price to zero and changed to SSO integration, we should
    #   no longer have discounts.
    if update_no_price or update_sso or update_change_price:
        if update_change_price:
            price = FAKE.random_int(min=0, max=100)
            assert_price = price if price else Decimal(0)
            contract.enrollment_fixed_price = price
        if update_no_price:
            contract.enrolment_fixed_price = None
        if update_sso:
            contract.integration_type = (
                CONTRACT_MEMBERSHIP_NONSSO if is_sso else CONTRACT_MEMBERSHIP_SSO
            )
            contract.membership_type = (
                CONTRACT_MEMBERSHIP_NONSSO if is_sso else CONTRACT_MEMBERSHIP_SSO
            )

        contract.save()
        ensure_enrollment_codes_exist(contract)

        if update_no_price and update_sso and not is_sso:
            # This is the last case, so we shouldn't have discounts now.
            # Test on our flags, not the contract, so we can make sure the contract
            # is also correct.
            assert contract.get_discounts().count() == 0
        else:
            # Otherwise we're really just making sure the price is updated.
            for code in contract.get_discounts():
                assert code.amount == assert_price
                assert code.products.filter(product=product).exists()


def test_ensure_enrollment_codes_clears_extras():
    """Test that ensure_enrollment_codes clears extra codes."""

    contract = ContractPageFactory.create(
        max_learners=10,
        integration_type=CONTRACT_MEMBERSHIP_NONSSO,
        membership_type=CONTRACT_MEMBERSHIP_NONSSO,
    )
    run = CourseRunFactory.create(b2b_contract=contract)
    product = ProductFactory.create(purchasable_object=run)

    created, updated, errors = ensure_enrollment_codes_exist(contract)

    assert created == 10
    assert updated == 0
    assert errors == 0

    random_extra_code = UnlimitedUseDiscountFactory.create()
    DiscountProduct.objects.create(discount=random_extra_code, product=product)

    assert contract.get_discounts().count() == 11

    created, updated, errors = ensure_enrollment_codes_exist(contract)

    assert created == 0
    assert updated == 11  # it updates all of them, then removes things
    assert errors == 1

    assert contract.get_discounts().count() == 10


@pytest.mark.parametrize("user_authenticated", [True, False])
@pytest.mark.parametrize("user_in_contract", [True, False])
@pytest.mark.parametrize("user_has_valid_edx_user", [True, False])
@pytest.mark.parametrize("product_in_contract", [True, False])
@pytest.mark.parametrize("price_is_zero", [True, False])
@pytest.mark.parametrize("cart_has_products", [True, False])
@pytest.mark.parametrize("cart_has_discounts", [True, False])
def test_create_b2b_enrollment(  # noqa: PLR0913, C901, PLR0915
    mocker,
    contract_ready_course,
    settings,
    user_authenticated,
    user_in_contract,
    user_has_valid_edx_user,
    product_in_contract,
    price_is_zero,
    cart_has_products,
    cart_has_discounts,
):
    """
    Test B2B enrollment generation.

    create_b2b_enrollment should check that we're allowed to enroll in the B2B
    courserun, and then create and process a basket for the user. If there's an
    enrollment code, it should use one. If the price specified is non-zero, that
    should be caught by the enrollment code.
    """

    mocker.patch("openedx.tasks.clone_courserun.delay")
    mocker.patch("openedx.api.enroll_in_edx_course_runs")
    mocker.patch("hubspot_sync.task_helpers.sync_hubspot_deal")
    mocker.patch("hubspot_sync.tasks.sync_deal_with_hubspot.apply_async")
    if not user_has_valid_edx_user:
        mocked_create_user = mocker.patch("openedx.api._create_edx_user_request")
    settings.OPENEDX_SERVICE_WORKER_API_TOKEN = "a token"  # noqa: S105
    settings.OPENEDX_SERVICE_WORKER_USERNAME = "a username"

    contract = factories.ContractPageFactory.create(
        integration_type=CONTRACT_MEMBERSHIP_SSO,
        membership_type=CONTRACT_MEMBERSHIP_SSO,
        enrollment_fixed_price=Decimal(0)
        if price_is_zero
        else FAKE.pydecimal(left_digits=2, right_digits=2, positive=True),
    )
    (course, _) = contract_ready_course
    run, product = create_contract_run(contract, course)

    if not product_in_contract:
        # just create something random - this is like someone fuzzing the API
        product = ProductFactory.create()

    if user_authenticated:
        user = UserFactory.create()
        if user_in_contract:
            user.b2b_contracts.add(contract)
            user.save()

        if not user_has_valid_edx_user:
            user.openedx_users.all().delete()

        assert Basket.objects.filter(user=user).count() == 0

        if cart_has_products:
            # create a basket - we should clear it out
            existing_basket = BasketFactory.create(user=user)
            BasketItemFactory(basket=existing_basket)

            if cart_has_discounts:
                # also put discounts in it!
                random_discount = UnlimitedUseDiscountFactory.create()
                BasketDiscount.objects.create(
                    redemption_date=now_in_utc(),
                    redeemed_by=user,
                    redeemed_discount=random_discount,
                    redeemed_basket=existing_basket,
                )

    else:
        user = AnonymousUser()

    # the request itself doesn't matter - we just need an object with a user in it
    request = RequestFactory().get("/")
    request.user = user

    result = create_b2b_enrollment(request, product)

    assert "result" in result

    if user_authenticated:
        # You should not have a basket by default. If you do, we should clear it
        # when you hit the enroll API.
        if not user_in_contract or not product_in_contract:
            assert_test = 1 if cart_has_products else 0
            assert Basket.objects.filter(user=user).count() == assert_test

        if not product_in_contract:
            assert result["result"] == USER_MSG_TYPE_B2B_ERROR_NO_PRODUCT
            return

        if not user_in_contract:
            assert result["result"] == USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT
            return

        if not price_is_zero:
            # Success, other than the price. We should bounce the user to the cart
            # page if the price isn't zero.
            assert result["result"] == USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT
            assert Basket.objects.filter(user=user).count() == 1
            test_basket = Basket.objects.filter(user=user).get()
            assert test_basket.basket_items.filter(product=product).exists()
            my_run_qs = CourseRunEnrollment.objects.filter(
                user=user, run=run, active=True
            )
            assert my_run_qs.count() == 0
            return

        # This is the success state.
        assert result["result"] == USER_MSG_TYPE_B2B_ENROLL_SUCCESS
        assert Basket.objects.filter(user=user).count() == 0

        if not user_has_valid_edx_user:
            mocked_create_user.assert_called()

        my_run_qs = CourseRunEnrollment.objects.filter(user=user, run=run, active=True)
        assert my_run_qs.count() == 1
        my_run = my_run_qs.first()
        assert my_run
        assert my_run.enrollment_mode == EDX_ENROLLMENT_VERIFIED_MODE
    else:
        assert result["result"] == USER_MSG_TYPE_B2B_DISALLOWED


@pytest.mark.parametrize(
    "run_exists",
    [
        True,
        False,
    ],
)
@pytest.mark.parametrize("source_run_exists", [True, False])
def test_create_contract_run(mocker, source_run_exists, run_exists):
    """
    Test creating runs for a contract.

    When we add courseware to a contract, we should check and create a run for
    the course. The run should have a readable ID in a known format. This should
    also queue up a course clone in edX.
    """

    contract = factories.ContractPageFactory.create()
    course = CourseFactory.create()
    source_course_key = CourseKey.from_string(f"{course.readable_id}+SOURCE")
    mocked_clone_run = mocker.patch("openedx.tasks.clone_courserun.delay")
    this_year = now_in_utc().year

    if source_run_exists:
        # This should be the default, but need to test the case in which the
        # source run isn't configured.
        source_course_run_key = (
            f"course-v1:{source_course_key.org}+{source_course_key.course}+SOURCE"
        )
        CourseRunFactory.create(
            course=course, courseware_id=source_course_run_key, run_tag="SOURCE"
        )

    target_course_id = f"{UAI_COURSEWARE_ID_PREFIX}{contract.organization.org_key}+{source_course_key.course}+{this_year}_C{contract.id}"

    if not source_run_exists:
        with pytest.raises(SourceCourseIncompleteError) as exc:
            create_contract_run(contract, course)

        assert "No course runs available" in str(exc)
        return

    if run_exists:
        collision_run = CourseRunFactory.create(
            course=course, courseware_id=target_course_id
        )

        with pytest.raises(TargetCourseRunExistsError) as exc:
            create_contract_run(contract, course)

        target_course_key = CourseKey.from_string(collision_run.courseware_id)
        assert f"courseware ID {target_course_key} already exists" in str(exc)
        return

    assert not course.courseruns.filter(courseware_id=target_course_id).exists()

    created_run, created_product = create_contract_run(contract, course)

    assert course.courseruns.filter(courseware_id=target_course_id).exists()
    assert created_run.courseware_id == target_course_id
    assert created_product.object_id == created_run.id
    assert settings.OPENEDX_COURSE_BASE_URL in created_run.courseware_url

    mocked_clone_run.assert_called()


def test_b2b_reconcile_user_orgs():  # noqa: PLR0915
    """Test that we can get a list of B2B orgs from somewhere and fix a user's associations."""

    user = UserFactory.create()
    organization_to_add = OrganizationPageFactory.create()
    organization_to_ignore = OrganizationPageFactory.create()
    organization_to_remove = OrganizationPageFactory.create()
    weird_organization = OrganizationPageFactory.create(sso_organization_id=None)

    assert user.b2b_contracts.count() == 0
    assert user.b2b_organizations.count() == 0

    # Step 1: pass in an org to a user that's not in anything
    # We should get back one addition, which is the org we're adding

    added, removed = reconcile_user_orgs(
        user, [organization_to_add.sso_organization_id]
    )

    assert added == 1
    assert removed == 0

    user.refresh_from_db()
    assert user.b2b_organizations.count() == 1
    assert user.b2b_organizations.filter(pk=organization_to_add.id).exists()
    assert not user.b2b_organizations.filter(pk=organization_to_ignore.id).exists()
    assert not user.b2b_organizations.filter(pk=organization_to_remove.id).exists()

    # Step 2: Add an org through a back channel, and then reconcile
    # The org should be removed

    UserOrganization.objects.create(
        user=user, organization=organization_to_remove, keep_until_seen=False
    )

    assert user.b2b_organizations.count() == 2

    added, removed = reconcile_user_orgs(
        user, [organization_to_add.sso_organization_id]
    )

    assert added == 0
    assert removed == 1

    user.refresh_from_db()
    assert user.b2b_organizations.count() == 1
    assert user.b2b_organizations.filter(pk=organization_to_add.id).exists()
    assert not user.b2b_organizations.filter(pk=organization_to_ignore.id).exists()
    assert not user.b2b_organizations.filter(pk=organization_to_remove.id).exists()

    # Step 3: Add the remove org, but set the flag so it should be kept now.

    UserOrganization.objects.create(
        user=user, organization=organization_to_remove, keep_until_seen=True
    )

    assert user.b2b_organizations.count() == 2

    added, removed = reconcile_user_orgs(
        user, [organization_to_add.sso_organization_id]
    )

    assert added == 0
    assert removed == 0

    user.refresh_from_db()
    assert user.b2b_organizations.count() == 2
    assert user.b2b_organizations.filter(pk=organization_to_add.id).exists()
    assert not user.b2b_organizations.filter(pk=organization_to_ignore.id).exists()
    assert user.b2b_organizations.filter(pk=organization_to_remove.id).exists()

    # Step 3.5: now reconcile with the remove org, we should clear the flag

    added, removed = reconcile_user_orgs(
        user,
        [
            organization_to_add.sso_organization_id,
            organization_to_remove.sso_organization_id,
        ],
    )

    assert added == 0
    assert removed == 0

    user.refresh_from_db()
    assert user.b2b_organizations.count() == 2
    assert user.b2b_organizations.filter(pk=organization_to_add.id).exists()
    assert not user.b2b_organizations.filter(pk=organization_to_ignore.id).exists()
    assert user.b2b_organizations.filter(pk=organization_to_remove.id).exists()

    # Step 4: add the weird org that doesn't have a UUID
    # Legacy non-manged orgs won't have a UUID, so we should leave them alone

    UserOrganization.objects.create(
        user=user, organization=weird_organization, keep_until_seen=False
    )

    added, removed = reconcile_user_orgs(
        user,
        [
            organization_to_add.sso_organization_id,
            organization_to_remove.sso_organization_id,
        ],
    )

    assert added == 0
    assert removed == 0

    user.refresh_from_db()
    assert user.b2b_organizations.count() == 3
    assert user.b2b_organizations.filter(pk=weird_organization.id).exists()


@pytest.mark.parametrize(
    "update_an_org",
    [
        True,
        False,
    ],
)
def test_b2b_reconcile_keycloak_orgs(mocker, update_an_org):
    """Test reconciliation of Keycloak orgs to OrganizationPages."""

    class MockedOrgModel:
        """A mocked organization model."""

        orgs = []

        def list(self):
            """Return a list of fake orgs."""

            return self.orgs

    org_model = MockedOrgModel()
    org_model.orgs = factories.OrganizationRepresentationFactory.create_batch(3)

    if update_an_org:
        existing_org = factories.OrganizationPageFactory.create()
        org_model.orgs.append(
            factories.OrganizationRepresentationFactory(
                id=existing_org.sso_organization_id,
                name="We changed the name",
                alias="changedKey",
                description="A new description",
            )
        )

    if not OrganizationIndexPage.objects.exists():
        factories.OrganizationIndexPageFactory.create()
    mocker.patch(
        "b2b.keycloak_admin_api.KeycloakAdminModel",
        return_value=org_model,
        autospec=True,
    )
    mocker.patch("b2b.keycloak_admin_api.bootstrap_client")

    created, updated = reconcile_keycloak_orgs()

    assert created == 3
    assert updated == (0 if not update_an_org else 1)

    org_pages = OrganizationPage.objects.filter(
        sso_organization_id__in=[mocked_org.id for mocked_org in org_model.orgs]
    ).all()

    assert len(org_pages) == (3 if not update_an_org else 4)

    found_count = 0

    for org_page in org_pages:
        for org in org_model.orgs:
            if str(org.id) == str(org_page.sso_organization_id):
                assert org_page.title == org.name
                if not update_an_org:
                    assert org_page.org_key == org.alias
                assert org_page.description == org.description
                found_count += 1

            if update_an_org and str(org_page.sso_organization_id) == str(
                existing_org.sso_organization_id
            ):
                assert org_page.title == "We changed the name"
                assert org_page.org_key != "changedKey"

    assert found_count == (3 if not update_an_org else 4)


def test_reconcile_bad_keycloak_org(mocker):
    """Test that reconciliation works when there's bad data"""

    existing_org_page = factories.OrganizationPageFactory.create()
    org = factories.OrganizationRepresentationFactory.create(
        alias=existing_org_page.org_key
    )

    if not OrganizationIndexPage.objects.exists():
        factories.OrganizationIndexPageFactory.create()

    page, _ = reconcile_single_keycloak_org(org)

    with pytest.raises(ValidationError) as exc:
        page.save()

    assert "Organization with this Org key already exists." in str(exc)


def test_reconcile_keycloak_org_without_description():
    """Test that reconciliation works when Keycloak org has no description"""

    if not OrganizationIndexPage.objects.exists():
        factories.OrganizationIndexPageFactory.create()

    # Test with None description (new org)
    org = factories.OrganizationRepresentationFactory.create(description=None)
    page, created = reconcile_single_keycloak_org(org)
    assert created is True
    assert page.description == ""

    parent_org_page = OrganizationIndexPage.objects.first()
    parent_org_page.add_child(instance=page)
    page.save()  # Should not raise IntegrityError

    # Test updating an existing org with None description
    org_update = factories.OrganizationRepresentationFactory.create(
        id=org.id, name="Updated Name", description=None
    )
    page_updated, created_update = reconcile_single_keycloak_org(org_update)
    assert created_update is False
    assert page_updated.description == ""
    page_updated.save()  # Should not raise IntegrityError


def test_user_add_b2b_org(mocked_b2b_org_attach):
    """Ensure adding a user to an organization works as expected."""

    orgs = OrganizationPageFactory.create_batch(2)
    user = UserFactory.create()

    # New-style ones
    contract_auto = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="auto",
        integration_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )
    contract_managed = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="managed",
        integration_type="managed",
        title="Contract Managed",
        name="Contract Managed",
    )
    contract_code = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="code",
        integration_type="code",
        title="Contract Enrollment Code",
        name="Contract Enrollment Code",
    )
    # Legacy ones - these will migrate to "managed" and "code"
    contract_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="sso",
        integration_type="sso",
        title="Contract SSO",
        name="Contract SSO",
    )
    contract_non_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="non-sso",
        integration_type="non-sso",
        title="Contract NonSSO",
        name="Contract NonSSO",
    )

    process_add_org_membership(user, orgs[0])

    # We should now be in the SSO, auto, and managed contracts
    # but not the other two.

    user.refresh_from_db()
    assert user.b2b_contracts.count() == 3
    assert user.b2b_organizations.filter(pk=orgs[0].id).exists()
    assert (
        user.b2b_contracts.filter(
            pk__in=[
                contract_auto.id,
                contract_sso.id,
                contract_managed.id,
            ]
        ).count()
        == 3
    )
    assert (
        user.b2b_contracts.filter(
            pk__in=[
                contract_code.id,
                contract_non_sso.id,
            ]
        ).count()
        == 0
    )


@pytest.mark.skip
def test_user_remove_b2b_org(mocked_b2b_org_attach):
    """Ensure removing a user from an org also clears the appropriate contracts."""

    orgs = OrganizationPageFactory.create_batch(2)
    user = UserFactory.create()

    # New-style ones
    contract_auto = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="auto",
        integration_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )
    contract_managed = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="managed",
        integration_type="managed",
        title="Contract Managed",
        name="Contract Managed",
    )
    contract_code = ContractPageFactory.create(
        organization=orgs[1],
        membership_type="code",
        integration_type="code",
        title="Contract Enrollment Code",
        name="Contract Enrollment Code",
    )
    # Legacy ones - these will migrate to "managed" and "code"
    contract_sso = ContractPageFactory.create(
        organization=orgs[0],
        membership_type="sso",
        integration_type="sso",
        title="Contract SSO",
        name="Contract SSO",
    )
    contract_non_sso = ContractPageFactory.create(
        organization=orgs[1],
        membership_type="non-sso",
        integration_type="non-sso",
        title="Contract NonSSO",
        name="Contract NonSSO",
    )

    managed_ids = [
        contract_auto.id,
        contract_managed.id,
        contract_sso.id,
    ]
    unmanaged_ids = [
        contract_code.id,
        contract_non_sso.id,
    ]

    process_add_org_membership(user, orgs[0])
    process_add_org_membership(user, orgs[1])

    user.b2b_contracts.add(contract_code)
    user.b2b_contracts.add(contract_non_sso)
    user.save()

    user.refresh_from_db()

    assert user.b2b_contracts.count() == 5

    process_remove_org_membership(user, orgs[1])

    assert user.b2b_contracts.filter(id__in=managed_ids).count() == 3
    assert user.b2b_contracts.filter(id__in=unmanaged_ids).count() == 0

    process_remove_org_membership(user, orgs[0])

    # we should have no contracts now since we're no longer in any orgs

    assert user.b2b_contracts.count() == 0


def test_b2b_contract_removal_keeps_enrollments(mocked_b2b_org_attach):
    """Ensure that removing a user from a B2B contract leaves their enrollments alone."""

    org = OrganizationPageFactory.create()
    user = UserFactory.create()

    contract_auto = ContractPageFactory.create(
        organization=org,
        membership_type="auto",
        integration_type="auto",
        title="Contract Auto",
        name="Contract Auto",
    )

    courserun = CourseRunFactory.create(b2b_contract=contract_auto)

    process_add_org_membership(user, org)

    CourseRunEnrollmentFactory(
        user=user,
        run=courserun,
    )

    user.refresh_from_db()

    assert courserun.enrollments.filter(user=user).count() == 1

    process_remove_org_membership(user, org)

    assert courserun.enrollments.filter(user=user).count() == 1


def test_b2b_org_attach_calls_keycloak(mocked_b2b_org_attach):
    """Test that attaching a user to an org calls Keycloak successfully."""

    org = OrganizationPageFactory.create()
    user = UserFactory.create()

    process_add_org_membership(user, org)

    mocked_b2b_org_attach.assert_called()


@pytest.mark.parametrize(
    ("run_exists", "import_succeeds"),
    [
        (True, True),  # Run exists, import call should not be made
        (False, True),  # Run doesn't exist, import succeeds
        (False, False),  # Run doesn't exist, import fails
    ],
)
def test_import_and_create_contract_run(mocker, run_exists, import_succeeds):
    """
    Test import_and_create_contract_run function.

    This function should:
    1. Check if the course run already exists
    2. If not, import it from edX using import_courserun_from_edx
    3. Create a contract run using the existing or imported run
    """
    # Setup test data
    contract = ContractPageFactory.create()
    department1 = DepartmentFactory.create(name="Engineering", slug="engineering")
    department2 = DepartmentFactory.create(name="Science", slug="science")
    departments = [department1, department2]

    course_run_id = "course-v1:MITx+6.00x+2T2023"

    # Mock the create_contract_run function
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_run = mocker.Mock()
    mock_course = mocker.Mock()
    mock_run.course = mock_course
    mock_product = mocker.Mock()
    mock_create_contract_run.return_value = (mock_run, mock_product)

    if run_exists:
        # Create a mock existing run
        existing_run = CourseRunFactory.create(courseware_id=course_run_id)

        # Test the case where run exists
        result = import_and_create_contract_run(
            contract=contract,
            course_run_id=course_run_id,
            departments=departments,
        )

        # Should use existing run and call create_contract_run
        mock_create_contract_run.assert_called_once_with(
            contract,
            existing_run.course,
            skip_edx=False,
            require_designated_source_run=False,
        )
        assert result == (mock_run, mock_product)
    else:
        # Mock import_courserun_from_edx
        mock_import = mocker.patch("courses.api.import_courserun_from_edx")

        if import_succeeds:
            # Mock successful import
            imported_run = mocker.Mock()
            imported_course = mocker.Mock()
            imported_run.course = imported_course
            mock_import.return_value = (imported_run, None, None)

            result = import_and_create_contract_run(
                contract=contract,
                course_run_id=course_run_id,
                departments=departments,
                live=True,
                create_cms_page=True,
            )

            # Verify import was called with correct parameters
            mock_import.assert_called_once_with(
                course_key=course_run_id,
                live=True,
                use_specific_course=None,
                departments=departments,
                create_depts=False,
                block_countries=None,
                price=None,
                create_cms_page=True,
                publish_cms_page=False,
                include_in_learn_catalog=False,
                ingest_content_files_for_ai=True,
                is_source_run=True,
            )

            # Verify create_contract_run was called with imported run
            mock_create_contract_run.assert_called_once_with(
                contract,
                imported_course,
                skip_edx=False,
                require_designated_source_run=False,
            )
            assert result == (mock_run, mock_product)
        else:
            # Mock failed import
            mock_import.return_value = None

            with pytest.raises(
                ValueError, match=r"Import and create contract run for .* failed"
            ):
                import_and_create_contract_run(
                    contract=contract,
                    course_run_id=course_run_id,
                    departments=departments,
                )

            mock_import.assert_called_once()
            mock_create_contract_run.assert_not_called()


def test_import_and_create_contract_run_with_all_kwargs(mocker):
    """Test import_and_create_contract_run with all possible keyword arguments."""
    contract = ContractPageFactory.create()
    departments = [DepartmentFactory.create()]
    course_run_id = "course-v1:MITx+6.00x+2T2023"

    # Mock import since run doesn't exist
    mock_import = mocker.patch("courses.api.import_courserun_from_edx")
    imported_run = mocker.Mock()
    imported_course = mocker.Mock()
    imported_run.course = imported_course
    mock_import.return_value = (imported_run, None, None)

    # Mock create_contract_run
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_run = mocker.Mock()
    mock_product = mocker.Mock()
    mock_create_contract_run.return_value = (mock_run, mock_product)

    # Test with all kwargs
    result = import_and_create_contract_run(
        contract=contract,
        course_run_id=course_run_id,
        departments=departments,
        live=False,
        use_specific_course="MITx+6.001x",
        create_depts=True,
        block_countries=["CN", "IR"],
        create_cms_page=False,
        publish_cms_page=True,
        include_in_learn_catalog=True,
        ingest_content_files_for_ai=False,
        skip_edx=True,
        require_designated_source_run=True,
    )

    # Verify import was called with all parameters
    mock_import.assert_called_once_with(
        course_key=course_run_id,
        live=False,
        use_specific_course="MITx+6.001x",
        departments=departments,
        create_depts=True,
        block_countries=["CN", "IR"],
        price=None,
        create_cms_page=False,
        publish_cms_page=True,
        include_in_learn_catalog=True,
        ingest_content_files_for_ai=False,
        is_source_run=True,
    )

    # Verify create_contract_run was called with kwargs
    mock_create_contract_run.assert_called_once_with(
        contract,
        imported_course,
        skip_edx=True,
        require_designated_source_run=True,
    )

    assert result == (mock_run, mock_product)


def test_import_and_create_contract_run_with_string_departments(mocker):
    """Test import_and_create_contract_run with department names as strings."""
    contract = ContractPageFactory.create()

    # Create departments and use their names as strings
    dept1 = DepartmentFactory.create(name="Engineering")
    dept2 = DepartmentFactory.create(name="Science")
    departments = [dept1.name, dept2.name]

    course_run_id = "course-v1:MITx+6.00x+2T2023"

    # Create existing run to avoid import path
    existing_run = CourseRunFactory.create(courseware_id=course_run_id)

    # Mock create_contract_run
    mock_create_contract_run = mocker.patch("b2b.api.create_contract_run")
    mock_run = mocker.Mock()
    mock_product = mocker.Mock()
    mock_create_contract_run.return_value = (mock_run, mock_product)

    result = import_and_create_contract_run(
        contract=contract,
        course_run_id=course_run_id,
        departments=departments,
    )

    # Should work with string department names
    mock_create_contract_run.assert_called_once_with(
        contract,
        existing_run.course,
        skip_edx=False,
        require_designated_source_run=False,
    )
    assert result == (mock_run, mock_product)


def test_get_runs_without_products():
    """Test that a run without products is caught by the validator."""

    contract = ContractPageFactory.create()

    run = CourseRunFactory.create(b2b_contract=contract)

    assert run in get_contract_runs_without_products(contract)


def test_get_contract_products_with_bad_pricing():
    """Test that products that have bad pricing are caught by the validator."""

    contract = ContractPageFactory.create(enrollment_fixed_price=19)

    run = CourseRunFactory.create(b2b_contract=contract)
    product = ProductFactory.create(price=76, purchasable_object=run)

    assert product in get_contract_products_with_bad_pricing(contract)


def test_ensure_contract_run_products():
    """Test that a run without products is caught by the validator."""

    contract = ContractPageFactory.create()

    run = CourseRunFactory.create(b2b_contract=contract)

    created_products = ensure_contract_run_products(contract)

    assert len(created_products) == 1
    assert created_products[0].purchasable_object == run


def test_ensure_contract_run_pricing():
    """Test that runs with bad pricing get fixed."""

    contract = ContractPageFactory.create(enrollment_fixed_price=19)

    run = CourseRunFactory.create(b2b_contract=contract)
    product = ProductFactory.create(price=76, purchasable_object=run)

    ensure_contract_run_pricing(contract)

    product.refresh_from_db()
    assert product.price == contract.enrollment_fixed_price


def test_remove_extra_codes():
    """
    Test that extra codes are removed for a contract/product as we expect.

    If there are too many codes for the product, it should remove the extras.
    It should additionally remove them from the _end_ of the list because the
    b2b_codes output command grabs the codes in database order.
    """

    contract = ContractPageFactory.create(
        membership_type=CONTRACT_MEMBERSHIP_NONSSO,
        integration_type=CONTRACT_MEMBERSHIP_NONSSO,
        max_learners=5,
    )
    run = CourseRunFactory.create(b2b_contract=contract)
    product = ProductFactory.create(price=76, purchasable_object=run)

    ensure_enrollment_codes_exist(contract)

    codes_we_should_keep = [
        code.discount_code for code in contract.get_discounts().all()
    ]

    assert len(codes_we_should_keep) == 5

    more_codes = OneTimeDiscountFactory.create_batch(5)

    for code in more_codes:
        DiscountProduct.objects.create(discount=code, product=product)

    assert contract.get_discounts().count() == 10

    # Just testing the extra code culling - don't want to run the whole stack

    removed_count = _handle_extra_enrollment_codes(contract, product)

    assert removed_count == 5

    codes_we_have = [code.discount_code for code in contract.get_discounts().all()]

    for code in codes_we_have:
        assert code in codes_we_should_keep
