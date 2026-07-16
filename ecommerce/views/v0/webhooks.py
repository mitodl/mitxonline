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
        should be able to validate the signature at this point.
        """

        try:
            stripe_event = api.PaymentGateway.perform_processor_response_validation(
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
        return True
