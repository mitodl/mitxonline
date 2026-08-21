"""
Seeds one fulfilled order per refund state, so the receipt page's refund panel
can be exercised without hand-building orders (mitodl/hq#12959).

The receipt reports a single `refund_status`, derived from the order's state,
the refund window, whether the order is B2B, and any request the learner has
already made. Each scenario below is a separate course and order, so one
learner's account covers every branch at once:

    eligible-audit    inside the window, course has an audit track
                      -> "Eligible until <date>", modal warns about losing
                         certificate-track access
    eligible-no-audit inside the window, course has no audit track
                      -> same card, but the modal warns the course disappears
    window-closed     purchased and started months ago
                      -> "Refund window closed", modal asks for a review and
                         takes free text instead of a preset reason
    requested         a request is pending
                      -> "Refund requested", no button
    denied            the request was turned down
                      -> "Refund declined", dated by when it was reviewed
    completed         refunded, with a refund transaction
                      -> "Refund completed" quoting the amount

The learner is enrolled in every run, so each scenario reaches their dashboard
and the course card links through to its receipt.

The sixth refund state, `ineligible`, is deliberately absent. It covers orders
that were never fulfilled and B2B contract orders, and neither reaches the
dashboard: order history carries fulfilled and refunded orders only, and B2B
enrollments are not shown there. Seeding one would produce a scenario that
cannot be walked the way the rest can. The receipt simply renders no refund
panel for them, which `ReceiptRefundCard` covers by unit test.

The learner is provisioned in **Keycloak** as well as Django, and the Django row
is stamped with the Keycloak ID. That link is not optional: login matches on
`global_id`, so a Django user without one is never matched and the login screen
loops.

Usage (local dev runs on the ol-infrastructure Tilt/k3d stack, not compose):
    kubectl exec -it -n mitxonline deploy/mitxonline-webapp -c app -- \\
        python manage.py seed_refund_scenarios

Re-running is safe: everything is keyed on Keycloak ID, email or readable ID and
rebuilt in place. Order dates are stored relative to "now" at seed time, so
re-run it once the eligible orders have aged past their refund window.
"""

import os
from datetime import timedelta
from decimal import Decimal

import requests
import reversion
from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.management import BaseCommand
from django.db import transaction
from django.utils import timezone
from reversion.models import Version

from courses.models import (
    Course,
    CourseRun,
    CourseRunEnrollment,
    Department,
    EnrollmentMode,
)
from ecommerce.constants import (
    REFUND_WINDOW_DAYS,
    TRANSACTION_TYPE_PAYMENT,
    TRANSACTION_TYPE_REFUND,
)
from ecommerce.models import (
    Line,
    Order,
    OrderStatus,
    Product,
    RefundReasonChoices,
    RefundRequest,
    RefundRequestStatus,
    Transaction,
)
from openedx.constants import EDX_ENROLLMENT_AUDIT_MODE, EDX_ENROLLMENT_VERIFIED_MODE
from users.models import User

DEPARTMENT_NAME = "Refund QA"
KC_TIMEOUT = 15
PRICE = Decimal("1574.60")

# `purchased` and `run_start` are day offsets from seed time. Anything older
# than REFUND_WINDOW_DAYS on both counts has missed its window.
SCENARIOS = (
    {
        "slug": "ELIGIBLE-AUDIT",
        "title": "Refundable, With Audit Track",
        "purchased": -1,
        "run_start": -5,
        "audit": True,
        "expectation": 'card reads "Eligible until <date>"; modal warns about losing certificate-track access',
    },
    {
        "slug": "ELIGIBLE-NO-AUDIT",
        "title": "Refundable, No Audit Track",
        "purchased": -1,
        "run_start": -5,
        "audit": False,
        "expectation": "same card; modal warns the course leaves the dashboard entirely",
    },
    {
        "slug": "WINDOW-CLOSED",
        "title": "Past The Refund Window",
        "purchased": -60,
        "run_start": -90,
        "audit": True,
        "expectation": 'card reads "Refund window closed"; modal asks for a review and takes free text',
    },
    {
        "slug": "REQUESTED",
        "title": "Refund Requested",
        "purchased": -2,
        "run_start": -5,
        "audit": True,
        "request": RefundRequestStatus.PENDING,
        "expectation": 'card reads "Refund requested" with the submission date, and offers no button',
    },
    {
        "slug": "DENIED",
        "title": "Refund Declined",
        "purchased": -40,
        "run_start": -60,
        "audit": True,
        "request": RefundRequestStatus.DENIED,
        "expectation": 'card reads "Refund declined", dated by when it was reviewed',
    },
    {
        "slug": "COMPLETED",
        "title": "Refund Completed",
        "purchased": -20,
        "run_start": -30,
        "audit": True,
        "refunded": True,
        "expectation": f'card reads "Refund completed" and quotes ${PRICE}',
    },
)


class Command(BaseCommand):
    """Seed one order per refund state, plus the learner who bought them."""

    help = __doc__

    def add_arguments(self, parser):
        """Parse arguments."""
        parser.add_argument(
            "--email",
            default="refund-qa@odl.local",
            help="Learner who owns every seeded order.",
        )
        parser.add_argument(
            "--password",
            default="localdev123",  # pragma: allowlist secret
            help="Keycloak password to set for the seeded user.",
        )
        parser.add_argument(
            "--keycloak-url",
            # KEYCLOAK_BASE_URL is what the app itself authenticates against, so
            # it is already correct for whichever stack this runs on.
            default=os.environ.get(
                "KEYCLOAK_BASE_URL",
                os.environ.get(
                    "KC_URL",
                    f"https://sso.ol.{os.environ.get('LOCAL_DEV_ROOT_DOMAIN', 'mit.dev')}",
                ),
            ),
            help="Keycloak base URL. (Default $KEYCLOAK_BASE_URL)",
        )
        parser.add_argument(
            "--keycloak-realm",
            default=os.environ.get("KEYCLOAK_REALM_NAME", "olapps"),
            help="Keycloak realm holding the local-dev users.",
        )
        parser.add_argument(
            "--keycloak-admin",
            default="admin",
            help="Keycloak master-realm admin username. (Default admin)",
        )
        parser.add_argument(
            "--keycloak-admin-password",
            default="admin",  # pragma: allowlist secret
            help="Keycloak master-realm admin password. (Default admin)",
        )
        parser.add_argument(
            "--skip-keycloak",
            action="store_true",
            help=(
                "Do not touch Keycloak. The Django user is still seeded, but "
                "without a Keycloak ID it cannot log in."
            ),
        )
        parser.add_argument(
            "--prefix",
            default="REFUND",
            help="Slug fragment used in the generated readable IDs.",
        )
        parser.add_argument(
            "--base-url",
            default=settings.MIT_LEARN_BASE_URL,
            help=(
                "MIT Learn base URL, used to print clickable receipt links. "
                "Defaults to MIT_LEARN_BASE_URL, which local stacks often leave "
                "at its production value — pass this to get working links."
            ),
        )

    # --------------------------------------------------------------- keycloak

    def _kc_token(self, opts):
        """Admin access token, or None if Keycloak is unreachable."""
        try:
            response = requests.post(
                f"{opts['keycloak_url']}/realms/master/protocol/openid-connect/token",
                data={
                    "client_id": "admin-cli",
                    "grant_type": "password",
                    "username": opts["keycloak_admin"],
                    "password": opts["keycloak_admin_password"],
                },
                timeout=KC_TIMEOUT,
            )
            response.raise_for_status()
            return response.json()["access_token"]
        except (requests.RequestException, KeyError, ValueError) as exc:
            self.stdout.write(
                self.style.WARNING(
                    f"  Keycloak unreachable at {opts['keycloak_url']}: {exc}"
                )
            )
            return None

    def _kc_ensure_user(self, token, opts, email):
        """
        Create the Keycloak user if absent and set its password.

        Returns the Keycloak ID, which becomes the Django user's global_id.
        """
        base = f"{opts['keycloak_url']}/admin/realms/{opts['keycloak_realm']}"
        headers = {"Authorization": f"Bearer {token}"}

        def find():
            response = requests.get(
                f"{base}/users",
                params={"email": email, "exact": "true"},
                headers=headers,
                timeout=KC_TIMEOUT,
            )
            response.raise_for_status()
            found = response.json()
            return found[0]["id"] if found else None

        try:
            kc_id = find()
            if kc_id is None:
                # 409 means it raced into existence; the re-find below covers it.
                requests.post(
                    f"{base}/users",
                    json={
                        "username": email,
                        "email": email,
                        "enabled": True,
                        # Skips the verification-email step, which would
                        # otherwise block login on a fresh local stack.
                        "emailVerified": True,
                    },
                    headers=headers,
                    timeout=KC_TIMEOUT,
                )
                kc_id = find()
            if kc_id is None:
                return None
            requests.put(
                f"{base}/users/{kc_id}/reset-password",
                json={
                    "type": "password",
                    "value": opts["password"],
                    "temporary": False,
                },
                headers=headers,
                timeout=KC_TIMEOUT,
            ).raise_for_status()
        except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
            self.stdout.write(
                self.style.WARNING(f"  Keycloak user {email} not provisioned: {exc}")
            )
            return None
        else:
            return kc_id

    # ------------------------------------------------------------------ user

    def _upsert_user(self, email, global_id):
        """
        Get or create the Django user, keyed on the Keycloak ID when we have one.

        Matching on global_id first matters: that is what the API gateway looks
        users up by, so a row found only by email but left unlinked is precisely
        the state that breaks login.
        """
        user = None
        if global_id:
            user = User.objects.filter(global_id=global_id).first()
        if user is None:
            user = User.objects.filter(email=email).first()

        if user is not None:
            if global_id and user.global_id != global_id:
                user.global_id = global_id
                user.save(update_fields=["global_id"])
            return user

        user = User.objects.create_user(
            username=email,
            email=email,
            name="Refund QA Learner",
            is_active=True,
        )
        if global_id:
            user.global_id = global_id
            user.save(update_fields=["global_id"])
        return user

    # -------------------------------------------------------------- courseware

    def _upsert_run(self, scenario, opts, now):
        """Build the course and run a scenario's order will point at."""
        department, _ = Department.objects.get_or_create(name=DEPARTMENT_NAME)
        readable_id = f"course-v1:{opts['prefix']}+{scenario['slug']}"

        course, _ = Course.objects.update_or_create(
            readable_id=readable_id,
            defaults={"title": scenario["title"], "live": True},
        )
        course.departments.add(department)

        start = now + timedelta(days=scenario["run_start"])
        run, _ = CourseRun.objects.update_or_create(
            courseware_id=f"{readable_id}+R1",
            defaults={
                "course": course,
                "title": scenario["title"],
                "run_tag": "R1",
                "start_date": start,
                "end_date": start + timedelta(days=120),
                "enrollment_start": start - timedelta(days=30),
                "live": True,
            },
        )

        # The audit track is what `has_free_audit` reports, and it decides which
        # consequence the refund modal warns about.
        verified, _ = EnrollmentMode.objects.get_or_create(
            mode_slug=EDX_ENROLLMENT_VERIFIED_MODE,
            defaults={"requires_payment": True},
        )
        audit, _ = EnrollmentMode.objects.get_or_create(
            mode_slug=EDX_ENROLLMENT_AUDIT_MODE,
            defaults={"requires_payment": False},
        )
        run.enrollment_modes.set([verified, audit] if scenario["audit"] else [verified])
        return run

    def _enroll(self, scenario, user, run):
        """
        Put the learner in the run so the course reaches their dashboard.

        The dashboard is built from enrollments, not orders, and its course card
        is what links through to the receipt. Without this the seeded orders are
        only reachable by typing a URL.

        A refunded order leaves the learner on the audit track, which is what the
        refund itself would have done to them.
        """
        mode = (
            EDX_ENROLLMENT_AUDIT_MODE
            if scenario.get("refunded")
            else EDX_ENROLLMENT_VERIFIED_MODE
        )
        CourseRunEnrollment.all_objects.update_or_create(
            user=user,
            run=run,
            defaults={
                "active": True,
                "change_status": None,
                "enrollment_mode": mode,
                # Nothing here talks to Open edX, so the enrollment is local only.
                "edx_enrolled": False,
            },
        )

    def _upsert_product(self, run):
        """A product for the run, with the reversion version an order line needs."""
        content_type = ContentType.objects.get_for_model(CourseRun)
        product = Product.all_objects.filter(
            content_type=content_type, object_id=run.id
        ).first()
        with reversion.create_revision():
            if product is None:
                product = Product.objects.create(
                    content_type=content_type,
                    object_id=run.id,
                    price=PRICE,
                    description=run.title,
                    is_active=True,
                )
            else:
                product.price = PRICE
                product.save()
        return product, Version.objects.get_for_object(product).last()

    # ------------------------------------------------------------------ order

    def _rebuild_order(self, scenario, user, run, now):
        """
        Replace this scenario's order outright.

        Rebuilding rather than updating keeps re-runs honest: an order's state,
        its refund requests and its transactions have to agree with each other,
        and patching a stale one into shape is more code than starting over.
        """
        _, version = self._upsert_product(run)
        Order.objects.filter(purchaser=user, lines__purchased_object_id=run.id).delete()

        state = scenario.get("state", OrderStatus.FULFILLED)
        order = Order.objects.create(
            purchaser=user, total_price_paid=PRICE, state=state
        )
        Line.objects.create(
            order=order,
            product_version=version,
            purchased_object_id=run.id,
            purchased_content_type=ContentType.objects.get_for_model(CourseRun),
            quantity=1,
        )

        purchased_at = now + timedelta(days=scenario["purchased"])
        Transaction.objects.create(
            order=order,
            transaction_id=f"seed-payment-{order.id}",
            amount=PRICE,
            transaction_type=TRANSACTION_TYPE_PAYMENT,
            data={"seeded": True},
        )

        if scenario.get("refunded"):
            order.state = OrderStatus.REFUNDED
            order.save(update_fields=["state"])
            refund = Transaction.objects.create(
                order=order,
                transaction_id=f"seed-refund-{order.id}",
                amount=PRICE,
                transaction_type=TRANSACTION_TYPE_REFUND,
                data={"seeded": True},
                reason="Seeded refund",
            )
            # `created_on` is auto_now_add, so it only moves via an UPDATE.
            Transaction.objects.filter(pk=refund.pk).update(
                created_on=purchased_at + timedelta(days=3)
            )

        request_status = scenario.get("request")
        if request_status:
            refund_request = RefundRequest.objects.create(
                order=order,
                user=user,
                refund_reason=RefundReasonChoices.NOT_ENOUGH_TIME,
                consent_given=True,
                status=request_status,
            )
            requested_at = purchased_at + timedelta(days=1)
            # updated_on is auto_now, and is what `refund_reviewed_on` reports.
            RefundRequest.objects.filter(pk=refund_request.pk).update(
                created_on=requested_at,
                updated_on=requested_at + timedelta(days=2),
            )

        Order.objects.filter(pk=order.pk).update(created_on=purchased_at)
        order.refresh_from_db()
        return order

    # ------------------------------------------------------------------- main

    @transaction.atomic
    def handle(self, *args, **options):  # noqa: ARG002
        """Seed the learner, the courseware and one order per refund state."""
        now = timezone.now()
        email = options["email"]

        global_id = None
        if not options["skip_keycloak"]:
            token = self._kc_token(options)
            if token:
                global_id = self._kc_ensure_user(token, options, email)

        user = self._upsert_user(email, global_id)

        rows = []
        for scenario in SCENARIOS:
            run = self._upsert_run(scenario, options, now)
            order = self._rebuild_order(scenario, user, run, now)
            self._enroll(scenario, user, run)
            rows.append((scenario, order))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Learner: {email}"))
        if global_id:
            self.stdout.write(f"  password: {options['password']}")
        else:
            self.stdout.write(
                self.style.WARNING(
                    "  No Keycloak ID — this user cannot log in. Re-run without "
                    "--skip-keycloak, or against a reachable Keycloak."
                )
            )
        self.stdout.write(
            f"  refund window: {REFUND_WINDOW_DAYS} days from purchase or course start"
        )
        self.stdout.write("")

        base = options["base_url"].rstrip("/")
        self.stdout.write(f"Dashboard: {base}/dashboard/")
        self.stdout.write("")

        for scenario, order in rows:
            self.stdout.write(
                self.style.SUCCESS(f"{scenario['slug']}  (order {order.id})")
            )
            self.stdout.write(f"  receipt:  {base}/receipt/{order.id}")
            self.stdout.write(f"  status:   {order.refund_status}")
            self.stdout.write(f"  expect:   {scenario['expectation']}")
            self.stdout.write("")
