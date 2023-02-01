// @flow

// Cart types

// Purchasable object can be one of a few things.
export type Product = {
  id: number,
  price: number,
  description: string,
  purchasable_object: any,
  is_active: boolean,
  product_flexible_price: Discount
}

export type BasketItem = {
  basket: number,
  product: Product,
  id: number
}

export type Purchaser = {
  first_name: ?string,
  last_name: ?string,
  email: ?string,
  country: ?string
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
  discount_type: string,
  payment_type: string
}

export type Refund = {
  amount: number,
  date: any
}

export type Line = {
  id: number,
  product: Product,
  quantity: number,
  item_description: string
}

export type Transactions = {
  name: ?string,
  payment_method: ?string,
  bill_to_email: ?string,
  card_type: ?string,
  card_number: ?string
}

export type StreetAddress = {
  city: ?string,
  postal_code: ?string,
  country: ?string,
  line: Array<string>
}

export type TransactionalLine = {
  start_date: ?string,
  end_date: ?string,
  readable_id: ?string,
  content_title: ?string,
  price: number,
  total_paid: number,
  quantity: number
}

export type OrderReceipt = {
  order: number,
  lines: Array<TransactionalLine>,
  id: number,
  total_price_paid: number,
  state: string,
  reference_number: string,
  discounts: Array<Discount>,
  refunds: Array<Refund>,
  created_on: string,
  transactions: Transactions,
  street_address: StreetAddress,
  purchaser: Purchaser
}
