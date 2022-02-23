import { pathOr } from "ramda"

import { getCsrfOptions, nextState } from "./util"

export const cartSelector = pathOr(null, ["entities", "cartItems"])
export const totalPriceSelector = pathOr(null, ["entities", "totalPrice"])
export const cartQueryKey = "cartItems"

export const checkoutPayloadSelector = pathOr(null, [
  "entities",
  "checkoutPayload"
])

export const cartQuery = () => ({
  queryKey:  cartQueryKey,
  url:       `/api/checkout/cart/`,
  transform: json => {
    const cartItems = json.basket_items.filter(
      item => item.product.purchasable_object !== null
    )

    return {
      cartItems:  cartItems,
      totalPrice: json.total_price
    }
  },
  update: {
    cartItems:  nextState,
    totalPrice: nextState
  }
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
