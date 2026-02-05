"""Plugin manager for MITx Online."""

import pluggy

from ecommerce import hookspecs as ecommerce_hookspecs


def get_plugin_manager():
    """Return the plugin manager for the app."""

    pm = pluggy.PluginManager("mitxonline")

    pm.add_hookspecs(ecommerce_hookspecs)

    pm.load_setuptools_entrypoints("mitxonline")
    return pm
