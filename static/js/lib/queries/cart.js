import { pathOr } from "ramda"

import { getCsrfOptions, nextState } from "./util"

export const cartSelector = pathOr(null, ["entities", "cartItems"])
export const totalPriceSelector = pathOr(null, ["entities", "totalPrice"])
export const orderHistorySelector = pathOr(null, ["entities", "orderHistory"])

export const discountedPriceSelector = pathOr(null, [
  "entities",
  "discountedPrice"
])
export const discountSelector = pathOr(null, ["entities", "discounts"])
export const cartQueryKey = "cartItems"
export const orderHistoryQueryKey = "orderHistory"
export const receiptQueryKey = "orderItems"

export const checkoutPayloadSelector = pathOr(null, [
  "entities",
  "checkoutPayload"
])

export const orderReceiptSelector = pathOr(null, ["entities", "orderReceipt"])

export const cartQuery = () => ({
  queryKey:  cartQueryKey,
  url:       `/api/checkout/cart/`,
  transform: json => {
    const cartItems = json.basket_items.filter(
      item => item.product.purchasable_object !== null
    )

    const discounts = json.discounts.map(item => item.redeemed_discount)

    return {
      cartItems:       cartItems,
      totalPrice:      json.total_price,
      discountedPrice: json.discounted_price,
      discounts:       discounts
    }
  },
  update: {
    cartItems:       nextState,
    totalPrice:      nextState,
    discountedPrice: nextState,
    discounts:       nextState
  },
  force: true
})

export const checkoutFormDataMutation = () => ({
  url:     `/api/checkout/start_checkout/`,
  options: {
    ...getCsrfOptions(),
    method: "POST"
  },
  transform: json => ({
    checkoutPayload: json
  }),
  update: {
    checkoutPayload: nextState
  }
})

export const orderHistoryQuery = () => ({
  url:       `/api/orders/history`,
  queryKey:  orderHistoryQueryKey,
  transform: json => ({
    orderHistory: json
  }),
  update: {
    orderHistory: nextState
  }
})
export const applyDiscountCodeMutation = (code: string) => ({
  url:  `/api/checkout/redeem_discount/`,
  body: {
    discount: code
  },
  options: {
    ...getCsrfOptions(),
    method: "POST"
  },
  update: {}
})

export const clearDiscountCodeMutation = () => ({
  url:     `/api/checkout/clear_discount/`,
  body:    {},
  options: {
    ...getCsrfOptions(),
    method: "POST"
  },
  update: {}
})

export const orderReceiptQuery = (orderId: number) => ({
  url:       `/api/orders/receipt/${orderId}/`,
  queryKey:  receiptQueryKey,
  transform: json => {
    const discounts = json.discounts.map(item => item.redeemed_discount)
    return {
      orderReceipt: json,
      discounts:    discounts
    }
  },
  update: {
    orderReceipt: nextState,
    discounts:    nextState
  }
})
