"""Plugin manager for MITx Online."""

import pluggy

from ecommerce import hookspecs as ecommerce_hookspecs
from ecommerce.hooks.process_transaction_line import CreateEnrollments


def get_plugin_manager():
    """Return the plugin manager for the app."""

    pm = pluggy.PluginManager("mitxonline")

    pm.add_hookspecs(ecommerce_hookspecs)

    pm.register(CreateEnrollments())

    pm.load_setuptools_entrypoints("mitxonline")
    return pm
