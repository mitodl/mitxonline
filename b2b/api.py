"""API functions for B2B operations."""

import logging
from decimal import Decimal
from urllib.parse import urljoin
from uuid import uuid4

import reversion
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count
from mitol.common.utils import now_in_utc
from opaque_keys.edx.keys import CourseKey
from wagtail.models import Page

from b2b.constants import B2B_RUN_TAG_FORMAT
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

    Contract runs are always self-paced. Dates align with the contract - start
    and end dates are set to the contract's start and end dates and the
    certificate available date is set to the start date of the contract. If the
    contract has no dates, then the start dates get set to today. The run tag
    will be generated according to the contract and org IDs.

    This will also create a product for the run. The product will have zero
    value (unless the contract specifies one).

    This won't create pages for either the run or the products, since they're
    not supposed to be accessed by the public.

    This will queue a task to create course runs in edX as appropriate.

    Args:
        contract (ContractPage): The contract to create the run for.
        course (Course): The course for which we should create a run.
    Returns:
        CourseRun: The created CourseRun object.
        Product: The created Product object.
    """

    # This probably needs some redefinition.
    # The courses we'll create these under are all going to be named something
    # like course-v1:UAI+CourseName+SOURCE (sometimes the org may be B2B or
    # something else).
    # We won't keep tabs on that particular course run. We will clone it, though.
    # The new course runs will be named this:
    # course-v1:ORGKEY+CourseName+yyyy_Cid
    # where ORGKEY is the key from the org record, CourseName comes from the
    # base course, yyyy is the current year, and id is the contract ID.

    run_tag = B2B_RUN_TAG_FORMAT.format(
        year=now_in_utc().year,
        contract_id=contract.id,
    )
    source_id = CourseKey.from_string(f"{Course.readable_id}+SOURCE")
    readable_id = (
        f"course-v1:{contract.organization.org_key}+{source_id.course}+{run_tag}"
    )

    # Check first for an existing run with the same tag.
    if CourseRun.objects.filter(course=course, b2b_contract=contract).exists():
        msg = f"Can't create a run for {course} and contract {contract}: run tag {run_tag} already exists."
        raise ValueError(msg)

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
        courseware_id=readable_id,
        run_tag=run_tag,
        start_date=start_date,
        end_date=end_date,
        enrollment_start=start_date,
        enrollment_end=end_date,
        certificate_available_date=start_date,
        is_self_paced=True,
        live=True,
        b2b_contract=contract,
        courseware_url_path=urljoin(settings.OPENEDX_COURSE_BASE_URL, readable_id),
    )
    course_run.save()
    clone_courserun.delay(course_run.id, base_id=source_id)

    log.debug(
        "Created run %s for course %s in contract %s", course_run, course, contract
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
            description=f"{contract.organization.name} - {course.title} {course.readable_id}",
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

    contract.save()

    return course_run, course_run_product


def validate_basket_for_b2b_purchase(request) -> bool:
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

    Returns: bool
    """
    from ecommerce.api import establish_basket

    basket = establish_basket(request)
    if not basket:
        return False

    nonfree_contracts = []
    free_contracts = []
    course_run_content_type = ContentType.objects.get_for_model(CourseRun)

    # Determine what contracts are linked to items in the basket.

    for item in (
        basket.basket_items.filter(product__content_type=course_run_content_type)
        .prefetch_related(
            "product",
            "product__purchasable_object",
            "product__purchasable_object__b2b_contract",
        )
        .all()
    ):
        contract = item.product.purchasable_object.b2b_contract

        if contract and contract.is_active:
            if contract.enrollment_fixed_price in (
                None,
                Decimal(0),
            ):
                free_contracts.append(contract)
            else:
                nonfree_contracts.append(contract)

    if len(nonfree_contracts) + len(free_contracts) == 0:
        # There aren't any, so we have nothing to validate.
        return True

    # Determine what free-to-attend contracts are in the cart, and also already
    # linked to the user. (We've pulled free-to-attend ones out above so just
    # use that list.)

    remaining_free_contract_qset = ContractPage.objects.filter(
        pk__in=free_contracts
    ).exclude(pk__in=request.user.b2b_contracts.all())

    if remaining_free_contract_qset.count() == 0 and len(nonfree_contracts) == 0:
        # The user's in all of the free ones, and there's no non-free ones,
        # so the basket is OK.
        return True

    # The basket includes products for free and/or non-free contracts. Check to
    # make sure we've got enrollment codes for these.

    check_contracts = [
        *remaining_free_contract_qset.all(),
        *nonfree_contracts,
    ]

    for check_contract in check_contracts:
        # Do the applied discounts in this basket apply to any of the products
        # in the basket? If not, then the basket is invalid.

        if (
            basket.discounts.filter(
                redeemed_discount__products__product__in=check_contract.get_products()
            ).count()
            == 0
        ):
            return False

    return True


def ensure_enrollment_codes_exist(contract: ContractPage):  # noqa: C901, PLR0915
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

    created = updated = errors = 0

    log.info("Checking enrollment codes for contract %s", contract)

    if contract.integration_type == "sso" and not contract.enrollment_fixed_price:
        # SSO contracts w/out price don't need discounts.
        discounts = contract.get_discounts()
        products = contract.get_products()

        log.info("Removing any existing discounts for SSO/free contract %s", contract)

        for discount in discounts:
            discount.products.filter(product__in=products).delete()
            discount.refresh_from_db()

            created += 1

            # Only delete the discount if there's no more products.
            # Otherwise, we might delete one that's shared for some reason.
            if discount.products.count() == 0:
                log.info(
                    "Contract %s: Existing discount %s no longer has products, removing",
                    contract,
                    discount,
                )
                discount.delete()
                updated += 1

        return (created, updated, errors)

    products = contract.get_products()

    log.info("Checking %s products for contract %s", len(products), contract)

    for product in products:
        # Check these things:
        # - Are there any discount codes?
        # - Are there enough discount codes (total, including redeemed ones)?

        discount_amount = contract.enrollment_fixed_price or 0
        product_discounts = (
            Discount.objects.filter(products__product=product).distinct().all()
        )

        if not contract.max_learners:
            # If we're doing unlimited seats, then we just need one discount per
            # product, set to Unlimited.

            if len(product_discounts) == 0:
                # Quick note: these are unlimited and not one-time-per-user because
                # there may be any number of courses the learner will want to
                # enroll in. That does mean that these codes need to be
                # protected. It's unlikely we'll have many unlimited-seat but
                # also not-SSO contracts, though.
                discount = Discount(
                    discount_code=uuid4(),
                    amount=discount_amount,
                    redemption_type=REDEMPTION_TYPE_UNLIMITED,
                    discount_type=DISCOUNT_TYPE_FIXED_PRICE,
                    payment_type=PAYMENT_TYPE_SALES,
                    is_bulk=True,
                )
                discount.save()

                discount_product = DiscountProduct(
                    discount=discount,
                    product=product,
                )
                discount_product.save()

                log.info(
                    "Contract %s: Created unlimited discount %s for product %s",
                    contract,
                    discount,
                    product,
                )

                created += 1
            elif len(product_discounts) == 1:
                Discount.objects.filter(pk=product_discounts[0].id).update(
                    **{
                        "amount": discount_amount,
                        "redemption_type": REDEMPTION_TYPE_UNLIMITED,
                        "discount_type": DISCOUNT_TYPE_FIXED_PRICE,
                        "payment_type": PAYMENT_TYPE_SALES,
                        "is_bulk": True,
                    }
                )

                product_discounts[0].refresh_from_db()

                log.info(
                    "Contract %s: updated discount %s for product %s",
                    contract,
                    product_discounts[0],
                    product,
                )

                if not product_discounts[0].products.filter(product=product).exists():
                    discount_product = DiscountProduct(
                        discount=product_discounts[0],
                        product=product,
                    )
                    discount_product.save()
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

            continue

        log.info(
            "Updating %s discount codes for product %s", len(product_discounts), product
        )

        for discount in product_discounts:
            Discount.objects.filter(pk=discount.id).update(
                **{
                    "amount": discount_amount,
                    "redemption_type": REDEMPTION_TYPE_ONE_TIME,
                    "discount_type": DISCOUNT_TYPE_FIXED_PRICE,
                    "payment_type": PAYMENT_TYPE_SALES,
                    "is_bulk": True,
                }
            )

            discount.refresh_from_db()

            log.info(
                "Contract %s: updated discount %s for product %s",
                contract,
                discount,
                product,
            )

            if not discount.products.filter(product=product).exists():
                discount_product = DiscountProduct(
                    discount=discount,
                    product=product,
                )
                discount_product.save()
                log.debug(
                    "Contract %s: Added product %s to discount %s",
                    contract,
                    product,
                    discount,
                )

            updated += 1

        create_count = contract.max_learners - len(product_discounts)

        log.info("Creating %s new discount codes for product %s", create_count, product)

        if create_count < 0:
            log.warning(
                "ensure_enrollment_codes_exist: Seat limited contract %s product %s has too many discount codes: %s - skipping create",
                contract,
                product,
                len(product_discounts),
            )
            continue

        for _ in range(create_count):
            discount = Discount(
                discount_code=uuid4(),
                amount=discount_amount,
                redemption_type=REDEMPTION_TYPE_ONE_TIME,
                discount_type=DISCOUNT_TYPE_FIXED_PRICE,
                payment_type=PAYMENT_TYPE_SALES,
                is_bulk=True,
            )
            discount.save()

            discount_product = DiscountProduct(
                discount=discount,
                product=product,
            )
            discount_product.save()

            created += 1

            log.info(
                "Contract %s: Created discount %s for product %s",
                contract,
                discount,
                product,
            )

    return (created, updated, errors)


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
    from ecommerce.api import establish_basket, generate_checkout_payload

    user = request.user
    if not user.is_authenticated:
        return {
            "result": main_constants.USER_MSG_TYPE_B2B_DISALLOWED,
        }

    purchasable_object = product.purchasable_object
    if not purchasable_object or not purchasable_object.b2b_contract:
        return {
            "result": main_constants.USER_MSG_TYPE_B2B_ERROR_NO_PRODUCT,
        }

    if not user.b2b_contracts.filter(id=purchasable_object.b2b_contract.id).exists():
        return {
            "result": main_constants.USER_MSG_TYPE_B2B_ERROR_NO_CONTRACT,
        }

    basket = establish_basket(request)
    item = BasketItem.objects.create(product=product, basket=basket, quantity=1)
    item.save()

    applicable_discounts_qs = product.discounts.annotate(
        redemptions=Count("discount__order_redemptions")
    ).filter(discount__is_bulk=True, redemptions=0, discount__products__product=product)
    if applicable_discounts_qs.count() > 0:
        # We have unused codes for this product, so we should apply one.
        # (If the contract isn't SSO, we'll have made a bunch of enrollment codes,
        # but we should still not make the user round-trip through ecommerce.)
        discount = applicable_discounts_qs.first().discount
        basket_discount = BasketDiscount.objects.create(
            redemption_date=now_in_utc(),
            redeemed_by=request.user,
            redeemed_discount=discount,
            redeemed_basket=basket,
        )
        basket_discount.save()

    basket_price = 0
    for basket_item in basket.basket_items.all():
        basket_price += basket_item.discounted_price

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
