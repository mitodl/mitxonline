// @flow
/* global SETTINGS: false */
import React from "react"
import { Button } from "reactstrap"
import {formatLocalePrice, roundPrice} from "../lib/util"

type Props = {
  totalPrice: number,
  orderFulfilled: boolean
}

export class OrderSummaryCard extends React.Component<Props> {
  renderDiscountUI(totalPrice: string) {
    return SETTINGS.features.enable_discount_ui ? (
      <div className="row order-summary-total">
        <div className="col-12 px-3 py-3 py-md-0">
          <div className="d-flex justify-content-between">
            <div className="flex-grow-1">
              Coupon applied (
              <em className="font-weight-bold text-primary">coupon1</em> )
            </div>
            <div className="ml-auto text-primary">-${totalPrice}</div>
          </div>
        </div>
      </div>
    ) : null
  }
  renderPayButton() {
    const { orderFulfilled, totalPrice } = this.props
    return totalPrice > 0 && !orderFulfilled ? (
      <>
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
      </>
    ) : null
  }
  renderAddCoupon() {
    return SETTINGS.features.enable_discount_ui ? (
      <div className="row">
        <div className="col-12 mt-4 px-3 py-3 py-md-0">
          Have a coupon?
          <div className="d-flex justify-content-between flex-sm-column flex-md-row">
            <input
              type="text"
              name="coupon-code"
              className="form-input flex-sm-grow-1"
            />
            <button className="btn btn-primary btn-red btn-halfsize mx-2 highlight font-weight-normal">
              Apply
            </button>
          </div>
          <div className="text-primary mt-2 font-weight-bold cart-text-smaller">
            Adding another coupon will replace the currently applied coupon.
          </div>
        </div>
      </div>
    ) : null
  }
  render() {
    let { totalPrice } = this.props
    const { orderFulfilled } = this.props
    totalPrice = formatLocalePrice(totalPrice)
    return (
      <div
        className="order-summary container card p-md-3 mb-4 rounded-0"
        key="ordersummarycard"
      >
        <div className="row order-summary-total mt-3 mt-md-0 mb-3">
          <div className="col-12 col-md-auto px-3 px-md-3">
            <h5>Order summary</h5>
          </div>
        </div>

        <div className="row">
          <div className="col-12 px-3 py-3 py-md-0">
            <div className="d-flex justify-content-between">
              <div className="flex-grow-1">Price</div>
              <div className="ml-auto">${totalPrice}</div>
            </div>
          </div>
        </div>
        {orderFulfilled ? null : this.renderDiscountUI(totalPrice)}
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
                <h5>${totalPrice}</h5>
              </div>
            </div>
          </div>
        </div>
        {orderFulfilled ? null : this.renderAddCoupon()}
        {orderFulfilled ? null : this.renderPayButton()}
      </div>
    )
  }
}
