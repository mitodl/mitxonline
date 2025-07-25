"""API functions for B2B operations."""

import logging
from collections.abc import Iterable
from decimal import Decimal
from typing import Union
from urllib.parse import quote, urljoin
from uuid import uuid4

import reversion
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from mitol.common.utils import now_in_utc
from opaque_keys.edx.keys import CourseKey
from wagtail.models import Page

from b2b.constants import B2B_RUN_TAG_FORMAT
from b2b.exceptions import SourceCourseIncompleteError, TargetCourseRunExistsError
from b2b.models import ContractPage, OrganizationIndexPage, OrganizationPage
from cms.api import get_home_page
from courses.models import Course, CourseRun
from ecommerce.constants import (
    DISCOUNT_TYPE_FIXED_PRICE,
    PAYMENT_TYPE_SALES,
    REDEMPTION_TYPE_ONE_TIME,
    REDEMPTION_TYPE_UNLIMITED,
)
from ecommerce.models import (
    Basket,
    BasketDiscount,
    BasketItem,
    Discount,
    DiscountProduct,
    Product,
)
from main import constants as main_constants
from main.utils import date_to_datetime
from openedx.tasks import clone_courserun

log = logging.getLogger(__name__)


def ensure_b2b_organization_index() -> OrganizationIndexPage:
    """
    Ensures that an index page has been created for signatories.
    """
    home_page = get_home_page()
    org_index_page = Page.objects.filter(
        content_type=ContentType.objects.get_for_model(OrganizationIndexPage)
    ).first()
    if not org_index_page:
        org_index_page = OrganizationIndexPage(title="Organizations")
        home_page.add_child(instance=org_index_page)
        org_index_page.save_revision().publish()

    if org_index_page.get_children_count() != OrganizationPage.objects.count():
        for org_page in OrganizationPage.objects.all():
            org_page.move(org_index_page, "last-child")
        log.info("Moved organization pages under organization index page")
    return org_index_page


def create_contract_run(
    contract: ContractPage, course: Course
) -> tuple[CourseRun, Product]:
    """
    Create a run for the specified contract.

    This does 3 main things:
    - Grab and identify the source course run, and create a new course key for
      the contract course run.
    - Create the contract course run in MITx Online, and queue a clone of the
      source course run in edX.
    - Create a product for the run.

    Source course runs are identified by looking for the most recent course run
    for the given course. This code expects you to pass in an MITx Online course
    that has a readable ID like 'course-v1:UAI_SOURCE+number` and that it has a
    run of some sort. This should just be a single run. If there's multiple runs,
    this code will grab the last one in the database.

    The MITx Online course run will belong to the source course. They will get a
    course key that is modified to represent the organization they belong to,
    the current year, and the contract ID. This means that the source course will
    have runs that have readable IDs that do not match the course ID.

    The course key is changed according to a set algorithm. For more information,
    see this discussion post: https://github.com/mitodl/hq/discussions/7525
    In general, this expects a course run that is in org `UAI_SOURCE` and then
    will create a new run that is `UAI_orgkey`, with a run tag that reflects
    the year we're creating the run in and the contract ID (`2025_C19` for
    instance).

    A product will be created for the new contract course run, and its price will
    either be zero or the amount specified by the contract. (Free courses still
    require either an association with the contract or an enrollment code for
    access.)

    Args:
        contract (ContractPage): The contract to create the run for.
        course (Course): The course for which we should create a run.
    Returns:
        CourseRun: The created CourseRun object.
        Product: The created Product object.
    """

    clone_course_run = course.courseruns.last()

    if not clone_course_run:
        msg = f"No course runs available for {course}."
        raise SourceCourseIncompleteError(msg)

    new_run_tag = B2B_RUN_TAG_FORMAT.format(
        year=now_in_utc().year,
        contract_id=contract.id,
    )
    source_id = CourseKey.from_string(clone_course_run.courseware_id)
    new_readable_id = f"course-v1:UAI_{contract.organization.org_key}+{source_id.course}+{new_run_tag}"

    # Check first for an existing run with the same readable ID.
    if CourseRun.objects.filter(course=course, courseware_id=new_readable_id).exists():
        msg = f"Can't create a run for {course} and contract {contract}: courseware ID {new_readable_id} already exists."
        raise TargetCourseRunExistsError(msg)

    start_date = (
        date_to_datetime(contract.contract_start, settings.TIME_ZONE)
        if contract.contract_start
        else now_in_utc()
    )
    end_date = (
        date_to_datetime(contract.contract_end, settings.TIME_ZONE)
        if contract.contract_end
        else None
    )

    course_run = CourseRun(
        course=course,
        title=course.title,
        courseware_id=new_readable_id,
        run_tag=new_run_tag,
        start_date=start_date,
        end_date=end_date,
        enrollment_start=start_date,
        enrollment_end=end_date,
        certificate_available_date=start_date,
        is_self_paced=True,
        live=True,
        b2b_contract=contract,
        courseware_url_path=urljoin(
            settings.OPENEDX_COURSE_BASE_URL, quote(new_readable_id)
        ),
    )
    course_run.save()
    clone_courserun.delay(course_run.id, base_id=clone_course_run.courseware_id)

    log.debug(
        "Created run %s for course %s in contract %s from course run %s",
        course_run,
        course,
        contract,
        clone_course_run,
    )

    content_type = ContentType.objects.filter(
        app_label="courses", model="courserun"
    ).get()

    with reversion.create_revision():
        course_run_product = Product(
            price=contract.enrollment_fixed_price
            if contract.enrollment_fixed_price
            else Decimal(0),
            is_active=True,
            description=f"{contract.organization.name} #{contract.id} - {course.title} {course.readable_id}",
            object_id=course_run.id,
            content_type=content_type,
        )
        course_run_product.save()

        log.debug(
            "Created product %s for run %s in contract %s",
            course_run_product,
            course_run,
            contract,
        )

    # Saving the contract here triggers any shoring up of related data that we
    # need to do, like generating enrollment codes.
    contract.save()

    return course_run, course_run_product


def get_free_and_nonfree_contracts(contracts: Iterable) -> tuple[list, list]:
    """
    Split contracts into free and non-free based on enrollment_fixed_price.

    Returns:
        (free_contracts, nonfree_contracts)
    """
    free, nonfree = [], []
    for c in contracts:
        price = c.enrollment_fixed_price
        (free if not price or price == 0 else nonfree).append(c)
    return free, nonfree


def is_discount_supplied_for_b2b_purchase(request, active_contracts=None) -> bool:
    """
    Check if a discount is supplied for B2B purchase.

    Args:
        request: The HTTP request object containing the basket data.
        active_contracts: List of active contracts to check against.

    Returns:
        bool: True if discount is supplied or not needed, False otherwise.
    """
    from ecommerce.api import establish_basket

    if not active_contracts:
        # No contracts = nothing to validate
        return True

    basket = establish_basket(request)
    if not basket:
        return False

    free_contracts, nonfree_contracts = get_free_and_nonfree_contracts(active_contracts)

    # Find free contracts the user is NOT associated with
    remaining_free_contract_qset = ContractPage.objects.filter(
        Q(pk__in=[c.pk for c in free_contracts])
        & ~Q(pk__in=request.user.b2b_contracts.values_list("pk", flat=True))
    )

    if not remaining_free_contract_qset.exists() and not nonfree_contracts:
        # Basket only has free contracts the user is part of — valid.
        return True

    return basket.discounts.exists()


def get_active_contracts_from_basket_items(basket: Basket):
    """Get active contracts from basket items with optimized queries."""
    course_run_ct = ContentType.objects.get_for_model(CourseRun)

    items = basket.basket_items.select_related("product__content_type").filter(
        product__content_type=course_run_ct
    )

    contract_ids = []
    for item in items:
        purchasable = item.product.purchasable_object
        if hasattr(purchasable, "b2b_contract") and purchasable.b2b_contract:
            contract_ids.append(purchasable.b2b_contract.id)

    if contract_ids:
        return list(ContractPage.objects.filter(id__in=contract_ids, active=True))

    return []


def validate_basket_for_b2b_purchase(request, active_contracts=None) -> bool:
    """
    Validate the basket for a B2B purchase.

    This function checks if the basket is valid for a B2B purchase. It ensures
    that the basket contains only products that are part of a contract and that
    the contract is active.

    If the integration is SSO, and there's no price, there won't be any
    applicable discounts and the basket shouldn't have any applied. In that case,
    we need to make sure the basket items all are either not B2B, or they are
    linked to contracts the user's also associated with.

    Args:
        request: The HTTP request object containing the basket data.

    Returns: bool, True if the basket is valid for B2B purchase, False otherwise.
    """
    from ecommerce.api import establish_basket

    basket = establish_basket(request)
    if not basket:
        return False

    free_contracts, nonfree_contracts = get_free_and_nonfree_contracts(active_contracts)

    # Find free contracts the user is NOT associated with
    remaining_free_contract_qset = ContractPage.objects.filter(
        Q(pk__in=[c.pk for c in free_contracts])
        & ~Q(pk__in=request.user.b2b_contracts.values_list("pk", flat=True))
    )

    if not remaining_free_contract_qset.exists() and not nonfree_contracts:
        # Basket only has free contracts the user is part of — valid.
        return True

    # Contracts that require validation via discount (user not in them, or not free)
    check_contracts = list(remaining_free_contract_qset) + nonfree_contracts

    # Gather all product IDs for these contracts
    product_ids = set()
    if check_contracts:
        for contract in check_contracts:
            product_ids.update(contract.get_products().values_list("pk", flat=True))

    # Validate that at least one discount applies to these products
    if product_ids:
        return basket.discounts.filter(
            redeemed_discount__products__product__in=product_ids
        ).exists()

    return True  # No products to validate means valid


def _get_discount_defaults(discount_amount: Decimal) -> dict:
    """Get default discount parameters."""
    return {
        "amount": discount_amount,
        "discount_type": DISCOUNT_TYPE_FIXED_PRICE,
        "payment_type": PAYMENT_TYPE_SALES,
        "is_bulk": True,
    }


def _create_discount_with_product(
    product: Product, discount_amount: Decimal, redemption_type: str
) -> Discount:
    """Create a discount and associate it with a product."""
    defaults = _get_discount_defaults(discount_amount)
    discount = Discount(
        discount_code=uuid4(),
        redemption_type=redemption_type,
        **defaults,
    )
    discount.save()

    discount_product = DiscountProduct(
        discount=discount,
        product=product,
    )
    discount_product.save()

    return discount


def _update_discount(
    discount: Discount, discount_amount: Decimal, redemption_type: str
) -> None:
    """Update an existing discount with new parameters."""
    defaults = _get_discount_defaults(discount_amount)
    Discount.objects.filter(pk=discount.id).update(
        redemption_type=redemption_type,
        **defaults,
    )


def _ensure_discount_product_association(discount: Discount, product: Product) -> bool:
    """Ensure a discount is associated with a product. Returns True if created."""
    if not discount.products.filter(product=product).exists():
        discount_product = DiscountProduct(
            discount=discount,
            product=product,
        )
        discount_product.save()
        return True
    return False


def _handle_sso_free_contract(contract: ContractPage) -> tuple[int, int, int]:
    """Handle SSO contracts without price by removing existing discounts."""
    created = updated = errors = 0
    discounts = contract.get_discounts()
    products = contract.get_products()

    log.info("Removing any existing discounts for SSO/free contract %s", contract)

    for discount in discounts:
        discount.products.filter(product__in=products).delete()
        discount.refresh_from_db()
        created += 1

        # Only delete the discount if there's no more products
        if discount.products.count() == 0:
            log.info(
                "Contract %s: Existing discount %s no longer has products, removing",
                contract,
                discount,
            )
            discount.delete()
            updated += 1

    return (created, updated, errors)


def _handle_unlimited_seats(
    contract: ContractPage, product: Product, product_discounts: list[Discount]
) -> tuple[int, int, int]:
    """Handle unlimited seat contracts by creating/updating one discount per product."""
    created = updated = errors = 0
    discount_amount = contract.enrollment_fixed_price or 0

    if len(product_discounts) == 0:
        discount = _create_discount_with_product(
            product, discount_amount, REDEMPTION_TYPE_UNLIMITED
        )
        log.info(
            "Contract %s: Created unlimited discount %s for product %s",
            contract,
            discount,
            product,
        )
        created += 1

    elif len(product_discounts) == 1:
        _update_discount(
            product_discounts[0], discount_amount, REDEMPTION_TYPE_UNLIMITED
        )
        product_discounts[0].refresh_from_db()

        log.info(
            "Contract %s: updated discount %s for product %s",
            contract,
            product_discounts[0],
            product,
        )

        if _ensure_discount_product_association(product_discounts[0], product):
            log.debug(
                "Contract %s: Added product %s to discount %s",
                contract,
                product,
                product_discounts[0],
            )
        updated += 1

    else:
        log.warning(
            "ensure_enrollment_codes_exist: Unlimited-seat contract %s product %s has too many discount codes: %s - skipping validation.",
            contract,
            product,
            len(product_discounts),
        )
        errors += 1

    return (created, updated, errors)


def _handle_limited_seats(
    contract: ContractPage, product: Product, product_discounts: list[Discount]
) -> tuple[int, int, int]:
    """Handle limited seat contracts by creating/updating multiple discounts."""
    created = updated = errors = 0
    discount_amount = contract.enrollment_fixed_price or 0

    log.info(
        "Updating %s discount codes for product %s", len(product_discounts), product
    )

    # Update existing discounts
    for discount in product_discounts:
        _update_discount(discount, discount_amount, REDEMPTION_TYPE_ONE_TIME)
        discount.refresh_from_db()

        log.info(
            "Contract %s: updated discount %s for product %s",
            contract,
            discount,
            product,
        )

        if _ensure_discount_product_association(discount, product):
            log.debug(
                "Contract %s: Added product %s to discount %s",
                contract,
                product,
                discount,
            )
        updated += 1

    # Create additional discounts if needed
    create_count = contract.max_learners - len(product_discounts)
    log.info("Creating %s new discount codes for product %s", create_count, product)

    if create_count < 0:
        log.warning(
            "ensure_enrollment_codes_exist: Seat limited contract %s product %s has too many discount codes: %s - skipping create",
            contract,
            product,
            len(product_discounts),
        )
        return (created, updated, errors)

    for _ in range(create_count):
        discount = _create_discount_with_product(
            product, discount_amount, REDEMPTION_TYPE_ONE_TIME
        )
        created += 1
        log.info(
            "Contract %s: Created discount %s for product %s",
            contract,
            discount,
            product,
        )

    return (created, updated, errors)


def ensure_enrollment_codes_exist(contract: ContractPage):
    """
    Ensure that enrollment codes exist for the given contract.

    If the contract is non-SSO or if it specifies a price, we need to create
    enrollment codes so the learners can enroll in the attached resources.

    Enrollment codes are discounts. When the contract is seat-limited, we create
    one discount code per learner per product. When the contract is unlimited,
    we create one discount code per product, and set it to unlimited redemptions.

    When the contract is created or modified, we'll need to shore up the discount
    codes appropriately:
    - If there's no discounts for any of the products, create them.
    - If there are discounts, make sure they apply to all the products that
      we've created, and create new ones if necessary.
    - If there are too many discounts, log a warning message.
    - If the contract is SSO and unlimited, but there are discounts for the
      products, clear those products out. (Also remove the discounts if there
      was only one product in the discount.)

    Note about SSO contracts: if there's no price, we don't create enrollment
    codes regardless of whether there's a learner cap or not. We'll limit the
    attachment when we log the user in.

    Returns:
        tuple: A tuple containing the number of created codes, updated codes,
        and codes with errors.
    """
    log.info("Checking enrollment codes for contract %s", contract)

    if contract.integration_type == "sso" and not contract.enrollment_fixed_price:
        # SSO contracts w/out price don't need discounts.
        return _handle_sso_free_contract(contract)

    products = contract.get_products()
    log.info("Checking %s products for contract %s", len(products), contract)

    total_created = total_updated = total_errors = 0

    for product in products:
        product_discounts = list(
            Discount.objects.filter(products__product=product).distinct()
        )

        if not contract.max_learners:
            # Unlimited seats - one discount per product
            created, updated, errors = _handle_unlimited_seats(
                contract, product, product_discounts
            )
        else:
            # Limited seats - multiple discounts per product
            created, updated, errors = _handle_limited_seats(
                contract, product, product_discounts
            )

        total_created += created
        total_updated += updated
        total_errors += errors

    return (total_created, total_updated, total_errors)


def _validate_b2b_enrollment_prerequisites(user, product: Product) -> Union[dict, None]:
    """
    Validate prerequisites for B2B enrollment.

    Returns:
        dict with error result if validation fails, None if validation passes.
    """
    if not user.is_authenticated:
        return {"result": main_constants.USER_MSG_TYPE_B2B_DISALLOWED}

    purchasable_object = product.purchasable_object
    if not purchasable_object or not purchasable_object.b2b_contract:
        return {"result": main_constants.USER_MSG_TYPE_B2B_ERROR_NO_PRODUCT}

    if not user.b2b_contracts.filter(id=purchasable_object.b2b_contract.id).exists():
        return {"result": main_constants.USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT}

    return None


def _prepare_basket_for_b2b_enrollment(request, product: Product) -> Basket:
    """
    Prepare basket for B2B enrollment by clearing it and adding the product.

    Returns:
        The prepared basket.
    """
    from ecommerce.api import establish_basket

    basket = establish_basket(request)
    # Clear the basket. For Unified Ecommerce, we may want to change this.
    # But MITx Online only allows one item per cart and not clearing it is confusing.
    basket.basket_items.all().delete()
    basket.discounts.all().delete()

    item = BasketItem.objects.create(product=product, basket=basket, quantity=1)
    item.save()

    return basket


def _apply_available_discount(request, product: Product, basket: Basket) -> None:
    """Apply available discount to the basket if one exists."""
    applicable_discounts_qs = product.discounts.annotate(
        redemptions=Count("discount__order_redemptions")
    ).filter(discount__is_bulk=True, redemptions=0, discount__products__product=product)

    if applicable_discounts_qs.exists():
        # We have unused codes for this product, so we should apply one.
        discount = applicable_discounts_qs.first().discount
        basket_discount = BasketDiscount.objects.create(
            redemption_date=now_in_utc(),
            redeemed_by=request.user,
            redeemed_discount=discount,
            redeemed_basket=basket,
        )
        basket_discount.save()


def create_b2b_enrollment(request, product: Product):
    """
    Create a B2B enrollment for the given product for the current user.

    If the contract doesn't specify a price and the user is associated with the
    contract, we should create an order and an enrollment for the user. Otherwise,
    we should redirect the user to the basket add API, so they can use an
    enrollment code that they already have.

    If the result is unsuccessful for a B2B-related reason, the "result" key in
    the dict will contain one of the USER_MSG_TYPE_B2B_ERROR constants. If the
    result instead would require payment, the "result" key will contain some
    additional information.
    - The basket price. The code will total the basket; if it's not zero, it will
      skip trying to check out and will instead return an error.
    - The result from generate_checkout_payload. This may contain a further error
      (if, say, the user fails the blocked country check, or they're in the course
      already). If the order instead just requires checkout, this will include the
      redirect for that - the frontend should send the user to the cart page in this
      case, though, so the user can see what's going on before they proceed.

    Args:
    - request: The HTTP request object containing the user and basket data.
    - product: The Product object representing the B2B product to enroll in.
    Returns: a dict containing
    - "result": the result of the attempt; one of the USER_MSG_TYPE_B2B constants.
    - "order": the order ID if the enrollment was successful and no checkout is needed.
    - "price": the total for the basket, if enrollment did not succeed
    - "checkout_result": the result of the checkout attempt, if applicable.
    """
    from ecommerce.api import generate_checkout_payload

    user = request.user

    # Validate prerequisites for B2B enrollment
    validation_error = _validate_b2b_enrollment_prerequisites(user, product)
    if validation_error:
        return validation_error

    # Prepare the basket for enrollment
    basket = _prepare_basket_for_b2b_enrollment(request, product)

    # Apply any available discount to the basket
    _apply_available_discount(request, product, basket)

    # Calculate basket total more efficiently
    basket_price = sum(item.discounted_price for item in basket.basket_items.all())

    if basket_price == 0:
        # This call should go ahead and fulfill the order.
        response = generate_checkout_payload(request)

        if "no_checkout" in response:
            return {
                "result": main_constants.USER_MSG_TYPE_B2B_ENROLL_SUCCESS,
                "order": response["order_id"],
            }
        else:
            return {
                "result": main_constants.USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT,
                "price": basket_price,
                "checkout_result": response,
            }

    return {
        "result": main_constants.USER_MSG_TYPE_B2B_ERROR_REQUIRES_CHECKOUT,
        "price": basket_price,
    }
