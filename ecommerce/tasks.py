from main.celery import app


@app.task
def send_ecommerce_order_receipt(order_id):
    from ecommerce.mail_api import send_ecommerce_order_receipt
    from ecommerce.models import Order

    order = Order.objects.get(pk=order_id)

    send_ecommerce_order_receipt(order)
