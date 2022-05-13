// @flow
import type { CurrentUser } from "./authTypes"

export type BasketItem = {
  basket: number,
  product: number
}

export type Basket = {
  user: CurrentUser,
  items: Array<BasketItem>
}

export type Product = {
  description: string,
  id: number,
  is_active: boolean,
  price: number
}
