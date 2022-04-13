// @flow
import { getCsrfOptions, nextState } from "./util"

export default {
  addProductToBasketMutation: (user: number, productId: number) => ({
    url:    `/api/baskets/${user}/items/`,
    body:   { product: productId },
    update: {
      basket: nextState
    },
    options: {
      ...getCsrfOptions(),
      method: "POST"
    }
  })
}
