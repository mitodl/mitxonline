"""
Webhook endpoints for ecommerce.

These are for handling events that are returned from the payment processors. As
such, they're specific to a particular payment processor and generally require
some authorization code that is also specific to the processor. So, these aren't
exposed via the OpenAPI spec.
"""

import logging

from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from mitol.payment_gateway import api, constants
from mitol.payment_gateway.exceptions import (
    BadStripeWebhookSecretError,
    ImproperStripeWebhookRequestError,
    NoStripeWebhookSecretError,
)
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from ecommerce.models import Order
from main.plugin_manager import get_plugin_manager

log = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
class StripeWebhookView(APIView):
    """API view for Stripe webhooks."""

    authentication_classes = []  # disables authentication

    event = None  # current Stripe event

    def check_permissions(self, request):
        """
        Check that the request is a valid Stripe webhook hit.

        Webhook hits all have the event data wrapped in a uniform container, and
        Stripe posts a signature along with the data that can be validated. We
        should be able to validate the signature at this point. The validation
        function returns the event payload, so this saves the payload so we don't
        have to do it again later.
        """

        log.info("check_permissions running")

        try:
            stripe_event = api.PaymentGateway.validate_processor_response(
                constants.MITOL_PAYMENT_GATEWAY_STRIPE,
                request,
            )
        except ImproperStripeWebhookRequestError:
            msg = "Received a response from Stripe that was unusable."
            log.exception(msg)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except (NoStripeWebhookSecretError, BadStripeWebhookSecretError):
            msg = "Could not validate the signature for the request."
            log.exception(msg)
            return Response(status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        self.event = stripe_event
        log.info("check_permissions got an event %s", stripe_event)
        return True

    def post(self, request, *args, **kwargs):  # noqa: ARG002
        """
        Process a Stripe webhook event.

        There's a pretty big library of Stripe events, only some of which we need
        to handle. This uses Pluggy hooks to dispatch handlers for the events
        we care about, and to do whatever global tasks need to be done for events.

        This is a webhook so returning anything but 200 is not particularly useful.
        If something fails in the hookimpls, log it there.
        """

        pm = get_plugin_manager()
        results = pm.hook.stripe_event(event=self.event)

        for i, result in enumerate(results):
            if isinstance(result, Order):
                log.info(
                    "StripeWebhookView: step %s: order %s is now %s",
                    i,
                    result.id,
                    result.state,
                )
            else:
                log.debug("StripeWebhookView: step %i: no data returned", i)

        return Response(status=status.HTTP_200_OK)
