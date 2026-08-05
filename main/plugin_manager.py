"""Plugin manager for MITx Online."""

import pluggy

from ecommerce import hookspecs as ecommerce_hookspecs
from ecommerce.hooks.process_transaction_line import CreateEnrollments
from ecommerce.hooks.stripe_webhooks import CheckoutSessionEvents


def get_plugin_manager():
    """Return the plugin manager for the app."""

    pm = pluggy.PluginManager("mitxonline")

    pm.add_hookspecs(ecommerce_hookspecs)

    pm.register(CreateEnrollments())
    pm.register(CheckoutSessionEvents())

    pm.load_setuptools_entrypoints("mitxonline")
    return pm
