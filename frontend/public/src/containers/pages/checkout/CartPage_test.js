// @flow
import { assert } from "chai"

import CartPage, { CartPage as InnerCartPage } from "./CartPage"
import IntegrationTestHelper from "../../../util/integration_test_helper"

describe("CartPage", () => {
  let helper, renderPage

  const anonymousUser = {
    id:               null,
    username:         "",
    email:            null,
    legal_address:    null,
    user_profile:     null,
    is_anonymous:     true,
    is_authenticated: false,
    is_staff:         false,
    is_superuser:     false,
    grants:           [],
    is_active:        false
  }

  const loggedInUser = {
    ...anonymousUser,
    id:               1,
    username:         "test",
    email:            "test@example.com",
    is_anonymous:     false,
    is_authenticated: true,
    is_active:        true
  }

  const cartItem = {
    product: {
      id:                 1,
      price:              "100.00",
      description:        "test product",
      purchasable_object: {
        course: {
          page: {
            financial_assistance_form_url: "https://example.com/fa"
          }
        }
      }
    }
  }

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    renderPage = helper.configureShallowRenderer(CartPage, InnerCartPage, {
      entities: {
        cartItems:       [cartItem],
        totalPrice:      100,
        discountedPrice: 100,
        discounts:       [],
        currentUser:     loggedInUser
      },
      queries: {
        cartItems: {
          isPending: false
        }
      }
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("shows the financial assistance offer link when the user is authenticated", async () => {
    const { inner } = await renderPage()
    assert.isOk(inner.instance().renderFinancialAssistanceOffer())
  })

  it("suppresses the financial assistance offer link when the user is logged out", async () => {
    const { inner } = await renderPage({
      entities: { currentUser: anonymousUser }
    })
    assert.isNull(inner.instance().renderFinancialAssistanceOffer())
  })

  it("passes isAuthenticated=true down to OrderSummaryCard when logged in", async () => {
    const { inner } = await renderPage()
    const summaryCard = inner.find("OrderSummaryCard")
    assert.isTrue(summaryCard.prop("isAuthenticated"))
  })

  it("passes isAuthenticated=false down to OrderSummaryCard when logged out", async () => {
    const { inner } = await renderPage({
      entities: { currentUser: anonymousUser }
    })
    const summaryCard = inner.find("OrderSummaryCard")
    assert.isFalse(summaryCard.prop("isAuthenticated"))
  })
})
