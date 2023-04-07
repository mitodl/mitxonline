// @flow
import React from "react"
import { Button, Badge } from "reactstrap"
import { formatLocalePrice } from "../lib/util"
import ApplyCouponForm from "./forms/ApplyCouponForm"
import type { Discount, Refund } from "../flow/cartTypes"

type Props = {
  totalPrice: number,
  orderFulfilled: boolean,
  discountedPrice: number,
  discounts: Array<Discount>,
  refunds: Array<Refund>,
  addDiscount?: Function,
  discountCode: string,
  cardTitle?: string
}

export class OrderSummaryCard extends React.Component<Props> {
  renderAppliedCoupons() {
    const { discounts } = this.props

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

    return (
      <div className="row order-summary-total">
        <div className="col-12 px-3 py-3 py-md-0">
          <div className="d-flex justify-content-between">
            <div className="flex-grow-1">
              Coupon applied (
              <em className="fw-bold text-primary">
                {discounts[0].discount_code}
              </em>{" "}
              )
            </div>
            <div className="ml-auto text-primary text-right">
              {discountAmountText}
            </div>
          </div>
        </div>
      </div>
    )
  }

  renderIndividualRefund(refund: Refund) {
    if (refund === null) {
      return null
    }

    const refundAmount = formatLocalePrice(Number(refund.amount))

    return (
      <div className="row order-summary-total">
        <div className="col-12 px-3 py-3 py-md-0">
          <div className="d-flex justify-content-between">
            <div className="flex-grow-1">
              <Badge className="bg-danger">Refund applied</Badge>
            </div>
            <div className="ml-auto text-primary text-right">
              {refundAmount}
            </div>
          </div>
        </div>
      </div>
    )
  }

  renderRefunds() {
    const { refunds } = this.props

    if (refunds === null || refunds.length === 0) {
      return null
    }

    const refundList = []

    for (let refund = 0; refund < refunds.length; refund++) {
      refundList.push(this.renderIndividualRefund(refunds[refund]))
    }

    return refundList
  }

  renderFulfilledTag() {
    const { orderFulfilled } = this.props

    if (orderFulfilled !== true) {
      return null
    }

    return (
      <div className="row order-summary-total">
        <div className="col-12 px-3 py-3 py-md-0">
          <div className="d-flex justify-content-between">
            <div className="flex-grow-1">
              <Badge className="bg-success float-right">Paid</Badge>
            </div>
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
      discountCode,
      cardTitle,
      refunds
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
            <h5 id="summary-card-title">{title}</h5>
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

        {this.renderAppliedCoupons()}

        {refunds === null || refunds.length === 0
          ? this.renderFulfilledTag()
          : this.renderRefunds()}

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

        {!orderFulfilled ? (
          <ApplyCouponForm
            onSubmit={addDiscount}
            couponCode={discountCode}
            discounts={discounts}
          />
        ) : null}

        {totalPrice > 0 && !orderFulfilled ? (
          <div className="row">
            <div className="col-12 text-center mt-4 mb-4">
              <Button
                type="link"
                className="btn btn-primary btn-gradient-red highlight fw-bold"
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
