"""JS interopability template tags"""

import json

from django import template
from django.utils.safestring import mark_safe

from main.utils import (
    get_js_settings,
    get_refine_datasources_settings,
    get_refine_oidc_settings,
)

register = template.Library()


@register.simple_tag(takes_context=True)
def js_settings(context):
    """Renders the JS settings object to a script tag"""
    request = context["request"]
    js_settings_json = json.dumps(get_js_settings(request))

    return mark_safe(  # noqa: S308
        f"""<script type="text/javascript">
var SETTINGS = {js_settings_json};
</script>"""
    )


@register.simple_tag(takes_context=True)
def refine_settings(context):
    """Renders the JS settings object to a script tag"""
    request = context["request"]
    oidc_settings_json = json.dumps(get_refine_oidc_settings(request))
    datasources_settings_json = json.dumps(get_refine_datasources_settings(request))

    return mark_safe(  # noqa: S308
        f"""<script type="text/javascript">
var OIDC_CONFIG = {oidc_settings_json};
var DATASOURCES_CONFIG = {datasources_settings_json}
</script>"""
    )
