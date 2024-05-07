----This script is to back-fill courses_paidcourserun for the imported MicroMaster orders (course runs)

INSERT INTO public.courses_paidcourserun (
    created_on,
    updated_on,
    course_run_id,
    order_id,
    user_id
)
SELECT
    mo_order.created_on,
    mo_order.updated_on,
    mo_line.purchased_object_id,
    mo_order.id,
    mo_order.purchaser_id
FROM public.ecommerce_order AS mo_order
JOIN public.ecommerce_line AS mo_line
    ON mo_order.id = mo_line.order_id
WHERE mo_order.reference_number LIKE 'MM%'
    AND mo_order.state = 'fulfilled'
ON CONFLICT DO NOTHING;
