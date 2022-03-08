// @flow

// Cart types

// Purchasable object can be one of a few things.
export type Product = {
  id: number,
  price: number,
  description: string,
  purchasable_object: any,
  is_active: boolean
}

export type BasketItem = {
  basket: number,
  product: Product,
  id: number
}

export type CartItem = {
  id: number,
  user: number,
  basket_items: Array<BasketItem>
}

export type PaginatedOrderHistory = {
  count: number,
  next: ?string,
  previous: ?string,
  results: Array<Object>
}

export type Discount = {
  id: number,
  amount: number,
  discount_code: string,
  discount_type: string
}
