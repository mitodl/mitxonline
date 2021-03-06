from main.celery import app


@app.task
def send_ecommerce_order_receipt(order_id):
    from ecommerce.mail_api import send_ecommerce_order_receipt
    from ecommerce.models import Order

    order = Order.objects.get(pk=order_id)

    send_ecommerce_order_receipt(order)


@app.task(acks_late=True)
def perform_unenrollment_from_order(order_id):
    """
    Task to perform unenrollment from courses against a specific order

    Args:
       order_id (int): Id of the order
    """
    from ecommerce.api import unenroll_learner_from_order

    unenroll_learner_from_order(order_id)
