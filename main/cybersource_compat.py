"""Compatibility shim for the CyberSource REST SDK's urllib3 usage.

cybersource-rest-client-python >= 0.0.70 calls urllib3.PoolManager/ProxyManager with
`keepalive_delay` and `keepalive_idle_window`, kwargs that exist only in urllib3-future:
https://github.com/CyberSource/cybersource-rest-client-python/blob/0.0.74/CyberSource/rest.py#L85-L94

We deliberately run the genuine urllib3 (see shims/urllib3-future/pyproject.toml). It accepts
unknown kwargs into `connection_pool_kw` at construction time and then fails on the first
request, when the pool key is built:

    TypeError: PoolKey.__new__() got an unexpected keyword argument 'key_keepalive_delay'

This module drops kwargs the real urllib3 cannot take, for the SDK only. The dropped options
tune urllib3-future's HTTP/2+ keep-alive pinging; real urllib3 has no equivalent knob and reuses
connections through its own pooling.
"""

from __future__ import annotations

import inspect
import logging
from functools import cache
from typing import Any

import urllib3
from urllib3.poolmanager import PoolKey

log = logging.getLogger(__name__)


@cache
def _supported_kwargs(manager_cls: type) -> frozenset[str]:
    """
    Return the kwarg names the real urllib3 accepts for a pool manager class.

    Two sources: the explicit __init__ parameters (num_pools, proxy_url, ...) and everything
    that can ride along in connection_pool_kw, which PoolKey's fields define exactly.
    """
    explicit = {
        name
        for name, param in inspect.signature(manager_cls.__init__).parameters.items()
        if param.kind is not param.VAR_KEYWORD and name != "self"
    }
    connection_pool_kw = {field.removeprefix("key_") for field in PoolKey._fields}
    return frozenset(explicit | connection_pool_kw)


def _drop_unsupported(manager_cls: type, kwargs: dict[str, Any]) -> dict[str, Any]:
    """Strip kwargs the real urllib3 would reject, recording what was dropped."""
    supported = _supported_kwargs(manager_cls)
    dropped = sorted(kwargs.keys() - supported)
    if dropped:
        log.debug(
            "Dropping urllib3-future-only kwargs from %s: %s",
            manager_cls.__name__,
            ", ".join(dropped),
        )
    return {key: value for key, value in kwargs.items() if key in supported}


class CompatUrllib3:
    """Stands in for the `urllib3` module inside CyberSource.rest."""

    def PoolManager(self, **kwargs: Any) -> urllib3.PoolManager:  # noqa: N802
        """Build a PoolManager, ignoring kwargs only urllib3-future understands."""
        return urllib3.PoolManager(**_drop_unsupported(urllib3.PoolManager, kwargs))

    def ProxyManager(self, **kwargs: Any) -> urllib3.ProxyManager:  # noqa: N802
        """Build a ProxyManager, ignoring kwargs only urllib3-future understands."""
        return urllib3.ProxyManager(**_drop_unsupported(urllib3.ProxyManager, kwargs))

    def __getattr__(self, name: str) -> Any:
        """Delegate everything else to the real urllib3 module."""
        return getattr(urllib3, name)


def apply_cybersource_urllib3_compat() -> None:
    """Point CyberSource.rest at a urllib3 that tolerates its urllib3-future kwargs."""
    from CyberSource import rest  # noqa: PLC0415

    if isinstance(rest.urllib3, CompatUrllib3):
        return

    rest.urllib3 = CompatUrllib3()
    # Class-level, process-wide cache - drop anything built before the patch.
    rest.RESTClientObject._urllib3_poolmanagers.clear()  # noqa: SLF001
