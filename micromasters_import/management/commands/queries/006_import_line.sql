--- Get the most recent product version of course runs
WITH recent_product_version AS (
    SELECT
        MAX(version.id) AS max_id,
        CAST(version.object_id AS integer) AS product_id
    FROM public.reversion_version AS version
    JOIN public.django_content_type AS content_type
        ON version.content_type_id = content_type.id
    JOIN public.ecommerce_product AS product
        ON CAST(version.object_id AS integer) = product.id
        AND product.is_active = true
    WHERE content_type.model = 'product'
      AND content_type.app_label = 'ecommerce'
    GROUP BY version.object_id
),
--- Get the corresponding course run id for the above most recent product version
courserun_product_version AS (
    SELECT
        product.object_id AS courserun_id,
        product_version.max_id AS product_version_id,
        courserun_type.id AS courserun_type_id
    FROM recent_product_version AS product_version
    JOIN public.ecommerce_product AS product
      ON product.id = product_version.product_id
    JOIN public.django_content_type AS courserun_type
      ON courserun_type.id = product.content_type_id
    WHERE courserun_type.app_label = 'courses'
      AND courserun_type.model = 'courserun'
)
INSERT INTO public.ecommerce_line (
    created_on,
    updated_on,
    quantity,
    order_id,
    product_version_id,
    purchased_content_type_id,
    purchased_object_id
)
SELECT
    mm_line.created_at,
    mm_line.modified_at,
    1,
    mo_order.id,
    courserun_product_version.product_version_id,
    courserun_product_version.courserun_type_id,
    courserun_product_version.courserun_id
FROM micromasters.ecommerce_order AS mm_order
JOIN micromasters.ecommerce_line AS mm_line
    ON mm_order.id = mm_line.order_id
JOIN public.courses_courserun AS mo_courserun
    ON mm_line.course_key = mo_courserun.courseware_id
JOIN courserun_product_version
    ON mo_courserun.id = courserun_product_version.courserun_id
JOIN public.ecommerce_order AS mo_order  -- orders are imported at this point
    ON mm_order.reference_number = mo_order.reference_number
ON CONFLICT DO NOTHING;