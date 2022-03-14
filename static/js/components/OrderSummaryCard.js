// @flow
/* global SETTINGS: false */
import React from "react"
import { Button } from "reactstrap"
import { formatLocalePrice, isSuccessResponse } from "../lib/util"
import ApplyCouponForm from "./forms/ApplyCouponForm"
import type { Discount } from "../flow/cartTypes"

type Props = {
  totalPrice: number,
  orderFulfilled: boolean,
  discountedPrice: number,
  discounts: Array<Discount>,
  addDiscount?: Function,
  clearDiscount?: Function,
  discountCode?: string,
  discountCodeIsBad: boolean,
  cardTitle?: string
}

export class OrderSummaryCard extends React.Component<Props> {
  renderAppliedCoupons() {
    const { discounts, clearDiscount, orderFulfilled } = this.props

    if (discounts === null || discounts.length === 0) {
      return null
    }

    let discountAmountText = null
    const discountAmount = Number(discounts[0].amount)

    switch (discounts[0].discount_type) {
    case "percent-off":
      discountAmountText = `${discountAmount}% off`
      break

    case "dollars-off":
      discountAmountText = `-${formatLocalePrice(discountAmount)}`
      break

    default:
      discountAmountText = `Fixed Price: ${formatLocalePrice(discountAmount)}`
      break
    }
    const clearDiscountLink = (
      <a href="#" className="text-primary" onClick={clearDiscount}>
        Clear Discount
      </a>
    )

    return (
      <div className="row order-summary-total">
        <div className="col-12 px-3 py-3 py-md-0">
          <div className="d-flex justify-content-between">
            <div className="flex-grow-1">
              Coupon applied (
              <em className="font-weight-bold text-primary">
                {discounts[0].discount_code}
              </em>{" "}
              )
              <br />
              {orderFulfilled ? null : clearDiscountLink}
            </div>
            <div className="ml-auto text-primary">{discountAmountText}</div>
          </div>
        </div>
      </div>
    )
  }
  render() {
    const {
      orderFulfilled,
      discountedPrice,
      totalPrice,
      discounts,
      addDiscount,
      discountCodeIsBad,
      discountCode,
      cardTitle
    } = this.props
    const fmtPrice = formatLocalePrice(totalPrice)
    const fmtDiscountPrice = formatLocalePrice(discountedPrice)
    const title = cardTitle ? cardTitle : "Order Summary"
    return (
      <div
        className="order-summary container card p-md-3 mb-4 rounded-0"
        key="ordersummarycard"
      >
        <div className="row order-summary-total mt-3 mt-md-0 mb-3">
          <div className="col-12 col-md-auto px-3 px-md-3">
            <h5>${title}</h5>
          </div>
        </div>

        <div className="row">
          <div className="col-12 px-3 py-3 py-md-0">
            <div className="d-flex justify-content-between">
              <div className="flex-grow-1">Price</div>
              <div className="ml-auto">{fmtPrice}</div>
            </div>
          </div>
        </div>

        {!SETTINGS.features.disable_discount_ui
          ? this.renderAppliedCoupons()
          : null}

        <div className="row my-3 mx-1">
          <div className="col-12 px-3 border-top border-dark" />
        </div>

        <div className="row order-summary-total">
          <div className="col-12 px-3 py-3 py-md-0">
            <div className="d-flex justify-content-between">
              <div className="flex-grow-1">
                <h5>Total</h5>
              </div>
              <div className="ml-auto">
                <h5>{fmtDiscountPrice || fmtPrice}</h5>
              </div>
            </div>
          </div>
        </div>

        {!SETTINGS.features.disable_discount_ui &&
        !orderFulfilled &&
        discountCode ? (
            <ApplyCouponForm
              onSubmit={addDiscount}
              discountCodeIsBad={discountCodeIsBad}
              couponCode={discountCode}
              discounts={discounts}
            />
          ) : null}

        {totalPrice > 0 && !orderFulfilled ? (
          <div className="row">
            <div className="col-12 text-center mt-4 mb-4">
              <Button
                type="link"
                className="btn btn-primary btn-gradient-red highlight font-weight-bold text-white"
                onClick={() => (window.location = "/checkout/to_payment")}
              >
                Place your order
              </Button>
            </div>
          </div>
        ) : null}

        {totalPrice > 0 && !orderFulfilled ? (
          <div className="row">
            <div className="col-12 px-3 py-3 py-md-0 cart-text-smaller">
              By placing my order I agree to the{" "}
              <a href="/terms-of-service/" target="_blank" rel="noreferrer">
                Terms of Service
              </a>
              , and{" "}
              <a href="/privacy-policy/" target="_blank" rel="noreferrer">
                Privacy Policy.
              </a>
            </div>
          </div>
        ) : null}
      </div>
    )
  }
}
