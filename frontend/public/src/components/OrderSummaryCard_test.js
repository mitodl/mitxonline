// @flow
import React from "react"
import sinon from "sinon"
import { shallow } from "enzyme"
import { assert } from "chai"

import { OrderSummaryCard } from "./OrderSummaryCard"
import ApplyCouponForm from "./forms/ApplyCouponForm"

describe("OrderSummaryCard", () => {
  let sandbox

  const baseProps = {
    totalPrice:      100,
    orderFulfilled:  false,
    discountedPrice: 100,
    discounts:       [],
    refunds:         [],
    discountCode:    ""
  }

  beforeEach(() => {
    sandbox = sinon.createSandbox()
  })

  afterEach(() => {
    sandbox.restore()
  })

  it("shows a paid-amount-off coupon as the gap between the basket prices", () => {
    const wrapper = shallow(
      <OrderSummaryCard
        {...baseProps}
        totalPrice={899}
        discountedPrice={799}
        discounts={[
          {
            id:            1,
            amount:        0,
            discount_code: "bought-child",
            discount_type: "paid-amount-off",
            payment_type:  "sales"
          }
        ]}
        isAuthenticated={true}
      />
    )

    assert.include(wrapper.text(), "-$100.00")
  })

  it("does not render the coupon form when logged out", () => {
    const wrapper = shallow(
      <OrderSummaryCard {...baseProps} isAuthenticated={false} />
    )
    assert.isFalse(wrapper.find(ApplyCouponForm).exists())
  })

  it("renders the coupon form when logged in", () => {
    const wrapper = shallow(
      <OrderSummaryCard {...baseProps} isAuthenticated={true} />
    )
    assert.isTrue(wrapper.find(ApplyCouponForm).exists())
  })

  it("still hides the coupon form when logged in but the order is fulfilled", () => {
    const wrapper = shallow(
      <OrderSummaryCard
        {...baseProps}
        orderFulfilled={true}
        isAuthenticated={true}
      />
    )
    assert.isFalse(wrapper.find(ApplyCouponForm).exists())
  })

  it("returns the anonymous checkout url when logged out", () => {
    const wrapper = shallow(
      <OrderSummaryCard {...baseProps} isAuthenticated={false} />
    )
    assert.equal(wrapper.instance().getCheckoutUrl(), "/checkout/anonymous/")
  })

  it("returns the authenticated checkout url when logged in", () => {
    const wrapper = shallow(
      <OrderSummaryCard {...baseProps} isAuthenticated={true} />
    )
    assert.equal(wrapper.instance().getCheckoutUrl(), "/checkout/to_payment")
  })

  it("redirects to the anonymous checkout url when placing an order while logged out", async () => {
    const originalDescriptor = Object.getOwnPropertyDescriptor(
      window,
      "location"
    )
    Object.defineProperty(window, "location", {
      writable:     true,
      configurable: true,
      value:        { href: "" }
    })

    try {
      const wrapper = shallow(
        <OrderSummaryCard {...baseProps} isAuthenticated={false} />
      )
      await wrapper.instance().handlePlaceOrder()

      assert.equal(window.location, "/checkout/anonymous/")
    } finally {
      // $FlowFixMe - originalDescriptor is always defined for window.location
      Object.defineProperty(window, "location", originalDescriptor)
    }
  })
})
