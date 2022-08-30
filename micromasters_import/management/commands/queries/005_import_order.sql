--The order import needs to join BOTH course run and product, otherwise it would insert orphan orders without any associated line items
--It also relies on reference_number from MicroMaster as identifier to check if orders are imported or not

INSERT INTO public.ecommerce_order (
    created_on,
    updated_on,
    state,
    total_price_paid,
    purchaser_id,
    reference_number
)
SELECT
    mm_order.created_at,
    mm_order.modified_at,
    mm_order.status,
    mm_order.total_price_paid,
    mo_user.id,
    mm_order.reference_number
FROM micromasters.ecommerce_order AS mm_order
JOIN micromasters.ecommerce_line AS mm_line
    ON mm_order.id = mm_line.order_id
JOIN micromasters.social_auth_usersocialauth AS mm_social
    ON mm_order.user_id = mm_social.user_id
JOIN public.users_user AS mo_user
    ON mm_social.uid = mo_user.username
JOIN public.courses_courserun AS mo_courserun
    ON mm_line.course_key = mo_courserun.courseware_id
JOIN public.ecommerce_product AS mo_product
    ON mo_courserun.id = mo_product.object_id
JOIN public.django_content_type AS content_type
   ON (mo_product.content_type_id = content_type.id
    AND content_type.app_label = 'courses'
    AND content_type.model = 'courserun')
LEFT JOIN public.ecommerce_order AS mo_order
    ON mm_order.reference_number = mo_order.reference_number
WHERE mm_order.status IN ('fulfilled', 'refunded', 'partially_refunded')
   AND mm_social.provider = 'mitxonline'
   AND mo_order.reference_number IS NULL;
