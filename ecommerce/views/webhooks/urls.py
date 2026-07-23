"""URL routing for webhooks."""

from django.urls import path

from ecommerce.views.webhooks import StripeWebhookView

urlpatterns = [
    path("stripe/", StripeWebhookView.as_view(), name="stripe_webhook_api"),
]
