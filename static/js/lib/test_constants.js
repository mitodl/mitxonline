// @flow
/* eslint-disable max-len */
export const CYBERSOURCE_CHECKOUT_RESPONSE = {
  payload: {
    access_key:                   "access_key",
    amount:                       "123.45",
    consumer_id:                  "staff",
    currency:                     "USD",
    locale:                       "en-us",
    override_custom_cancel_page:  "https://micromasters.mit.edu?cancel",
    override_custom_receipt_page: "https://micromasters.mit.edu?receipt",
    profile_id:                   "profile_id",
    reference_number:             "MM-george.local-56",
    signature:                    "56ItDy52E+Ii5aXhiq89OwRsImukIQRQetaHVOM0Fug=",
    signed_date_time:             "2016-08-24T19:07:57Z",
    signed_field_names:
      "access_key,amount,consumer_id,currency,locale,override_custom_cancel_page,override_custom_receipt_page,profile_id,reference_number,signed_date_time,signed_field_names,transaction_type,transaction_uuid,unsigned_field_names",
    transaction_type:     "sale",
    transaction_uuid:     "uuid",
    unsigned_field_names: ""
  },
  url:    "https://testsecureacceptance.cybersource.com/pay",
  method: "POST"
}

export const ORDER_RECEIPT_OBJECT = {
  id:               1,
  created_on:       "2019-10-09T09:47:09.219354Z",
  reference_number: "mitxonline-dev-1",
  purchaser:        1,
  total_price_paid: "200",
  state:            "fulfilled",
  lines:            [
    {
      id:               2,
      item_description: "sdfgsdgfs",
      product:          {
        id:                 2,
        price:              "35.00",
        description:        "sdfgsdgfs",
        is_active:          true,
        purchasable_object: {}
      },
      quantity:    1,
      total_price: 35,
      unit_price:  35
    }
  ],
  discounts: [
    {
      redeemed_discount: {
        amount:          "0.00000",
        automatic:       false,
        created_on:      "2022-03-09T19:49:39.409600Z",
        discount_code:   "NOMA",
        discount_type:   "fixed-price",
        id:              2,
        max_redemptions: 5,
        redemption_type: "one-time",
        updated_on:      "2022-03-10T16:42:45.883756Z"
      }
    }
  ]
}
