import casual from "casual-browserify"
import { incrementer } from "../lib/util"
import { AnonymousUser, LoggedInUser, UnusedCoupon } from "../types/auth"

const incr = incrementer()
export const makeAnonymousUser = (): AnonymousUser => ({
  is_anonymous:     true,
  is_authenticated: false
})
export const makeUnusedCoupon = (): UnusedCoupon => ({
  product_id:      incr.next().value,
  coupon_code:     casual.word,
  expiration_date: casual.moment.format()
})
export const makeUser = (
  username?: string | null | undefined
): LoggedInUser => ({
  id:               incr.next().value,
  username:         username || `${casual.word}_${incr.next().value}`,
  email:            casual.email,
  name:             casual.full_name,
  is_anonymous:     false,
  is_authenticated: true,
  is_editor:        false,
  created_on:       casual.moment.format(),
  updated_on:       casual.moment.format(),
  legal_address:    {
    street_address:     [casual.street],
    first_name:         casual.first_name,
    last_name:          casual.last_name,
    city:               casual.city,
    state_or_territory: "US-MA",
    country:            "US",
    postal_code:        "02090"
  }
})
export const makeCountries = () => [
  {
    code:   "US",
    name:   "United States",
    states: [
      {
        code: "US-CO",
        name: "Colorado"
      },
      {
        code: "US-MA",
        name: "Massachusetts"
      }
    ]
  },
  {
    code:   "CA",
    name:   "Canada",
    states: [
      {
        code: "CA-QC",
        name: "Quebec"
      },
      {
        code: "CA-NS",
        name: "Nova Scotia"
      }
    ]
  },
  {
    code:   "FR",
    name:   "France",
    states: []
  },
  {
    code:   "GB",
    name:   "United Kingdom",
    states: []
  }
]
