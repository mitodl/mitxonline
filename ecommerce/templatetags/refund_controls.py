from django import template
from django.contrib.admin.templatetags.admin_modify import submit_row

register = template.Library()


@register.inclusion_tag("admin/ecommerce/refund_control_row.html", takes_context=True)
def refund_order_buttons(context):
    context["show_close"] = True

    return submit_row(context)
