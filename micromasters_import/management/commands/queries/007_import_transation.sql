INSERT INTO public.ecommerce_transaction (
    transaction_id,
    amount,
    data,
    order_id,
    transaction_type,
    reason,
    created_on,
    updated_on
)
SELECT
    mm_receipt.data->>'transaction_id',
    mm_order.total_price_paid,
    mm_receipt.data,
    mo_order.id,
    CASE
         WHEN mm_order.status IN ('refunded', 'partially_refunded') THEN 'refund'
         ELSE 'payment'
    END,
    '', --- leave it as blank for reason
    mm_receipt.created_at,
    mm_receipt.modified_at
FROM micromasters.ecommerce_receipt AS mm_receipt
JOIN micromasters.ecommerce_order AS mm_order
   ON mm_receipt.order_id = mm_order.id
JOIN public.ecommerce_order AS mo_order
   ON mm_order.reference_number = mo_order.reference_number
WHERE mm_receipt.data->>'transaction_id' IS NOT NULL
ON CONFLICT DO NOTHING;
