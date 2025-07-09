// @flow
import React from "react"
import { Formik, FormikProps } from "formik"
// $FlowFixMe
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

type FormValues = {
  couponCode: string
}

type State = {
  submittingPlaceOrder: boolean
}

export class OrderSummaryCard extends React.Component<Props, State> {
  formikRef: { current: null | FormikProps<FormValues> } = React.createRef()

  state = {
    submittingPlaceOrder: false
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

  renderIndividualRefund(refund: Refund) {
    if (refund === null) {
      return null
    }

    const refundAmount = formatLocalePrice(Number(refund.amount))

    return (
      <div className="d-flex justify-content-between">
        <div className="flex-grow-1">
          <Badge className="bg-danger">Refund applied</Badge>
        </div>
        <div className="ml-auto text-primary text-end">{refundAmount}</div>
      </div>
    )
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
      <div className="d-flex justify-content-between">
        <div className="flex-grow-1 w-75">
          Coupon applied (
          <em className="fw-bold text-primary">{discounts[0].discount_code}</em>{" "}
          )
        </div>
        <div className="ml-auto text-primary text-end">
          {discountAmountText}
        </div>
      </div>
    )
  }

  handlePlaceOrder = async () => {
    const formik = this.formikRef.current
    const { discounts } = this.props

    // If there's already a discount applied and no new coupon code, proceed to payment
    if (discounts && discounts.length > 0 && 
        (!formik || !formik.values.couponCode || !formik.values.couponCode.trim())) {
      window.location = "/checkout/to_payment"
      return
    }

    // Check if formik exists and couponCode has a value
    if (formik && formik.values.couponCode && formik.values.couponCode.trim()) {
      // Flag this is from Place Order button
      this.setState({ submittingPlaceOrder: true })
      await formik.submitForm()
    } else {
      // No coupon code, proceed directly to payment
      window.location = "/checkout/to_payment"
    }
  }

  clearCouponField() {
    if (this.formikRef.current) {
      this.formikRef.current.setFieldValue("couponCode", "")
      this.formikRef.current.resetForm({ values: { couponCode: "" } })
    }
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
    
    // Only show discount code in field if there's no discount already applied
    const initialCouponCode = (discounts && discounts.length > 0) ? "" : discountCode

    return (
      <div className="order-summary container std-card" key="ordersummarycard">
        <div className="std-card-body checkout-page">
          <h3 id="summary-card-title">{title}</h3>

          <div className="order-pricing-info">
            <div className="d-flex justify-content-between">
              <div className="flex-grow-1">Price</div>
              <div className="ml-auto">{fmtPrice}</div>
            </div>

            {this.renderAppliedCoupons()}
            {refunds === null || refunds.length === 0 ?
              this.renderFulfilledTag() :
              this.renderRefunds()}
          </div>

          <div className="d-flex justify-content-between">
            <div className="flex-grow-1">
              <h5>Total</h5>
            </div>
            <div className="ml-auto">
              <h5>{fmtDiscountPrice || fmtPrice}</h5>
            </div>
          </div>

          {!orderFulfilled ? (
            <Formik
              innerRef={this.formikRef}
              initialValues={{ couponCode: initialCouponCode }}
              enableReinitialize={true}
              onSubmit={async (values, formikHelpers) => {
                if (addDiscount) {
                  await addDiscount(values, formikHelpers)

                  const hasErrors =
                    Object.keys(formikHelpers.errors).length > 0 ||
                    (formikHelpers.status && formikHelpers.status.error)

                  if (!hasErrors) {
                    // Clear the coupon code field after successful application
                    this.clearCouponField()
                    
                    if (this.state.submittingPlaceOrder) {
                      // Redirect only if there were no errors and this was from Place Order button
                      window.location = "/checkout/to_payment"
                    }
                  }

                  // Reset flag
                  this.setState({ submittingPlaceOrder: false })
                }
              }}
            >
              <ApplyCouponForm discounts={discounts} />
            </Formik>
          ) : null}

          {(totalPrice > 0 || discounts) && !orderFulfilled ? (
            <div>
              <Button
                id="place-order-button"
                className="btn btn-primary btn-gradient-red-to-blue btn-place-order"
                onClick={this.handlePlaceOrder}
              >
                Place your order
              </Button>
            </div>
          ) : null}

          {(totalPrice > 0 || discounts) && !orderFulfilled ? (
            <div className="cart-text-smaller">
              By placing my order I agree to the{" "}
              <a href="/terms-of-service/" target="_blank" rel="noreferrer">
                Terms of Service
              </a>
              , and{" "}
              <a href="/privacy-policy/" target="_blank" rel="noreferrer">
                Privacy Policy.
              </a>
            </div>
          ) : null}
        </div>
      </div>
    )
  }
}
