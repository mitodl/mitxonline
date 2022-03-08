// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import {
  ALERT_TYPE_DANGER,
  ALERT_TYPE_SUCCESS,
  CART_DISPLAY_PAGE_TITLE
} from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest, mutateAsync } from "redux-query"
import { createStructuredSelector } from "reselect"

import type { BasketItem, Discount } from "../../../flow/cartTypes"

import Loader from "../../../components/Loader"

import {
  cartQuery,
  cartSelector,
  totalPriceSelector,
  discountedPriceSelector,
  discountSelector,
  applyDiscountCodeMutation,
  clearDiscountCodeMutation
} from "../../../lib/queries/cart"

import type { RouterHistory } from "react-router"
import moment from "moment"
import {
  formatPrettyDateTimeAmPmTz,
  parseDateString,
  isSuccessResponse,
  formatLocalePrice
} from "../../../lib/util"
import { Button } from "reactstrap"
import { addUserNotification } from "../../../actions"

import ApplyCouponForm from "../../../components/forms/ApplyCouponForm"

type Props = {
  history: RouterHistory,
  cartItems: Array<BasketItem>,
  totalPrice: number,
  discountedPrice: number,
  discounts: Array<Discount>,
  isLoading: boolean,
  applyDiscountCode: (code: string) => Promise<any>,
  clearDiscountCode: () => Promise<any>,
  addUserNotification: Function,
  forceRequest: Function
}

type CartState = {
  discountCode: string,
  discountCodeIsBad: boolean
}

export class CartPage extends React.Component<Props, CartState> {
  state = {
    discountCode:      "",
    discountCodeIsBad: false
  }

  updateCode(event: Object) {
    this.setState({
      discountCode:      event.target.value,
      discountCodeIsBad: false
    })
  }

  async addDiscount(ev: Object) {
    const subbedCode = ev.couponCode
    const { applyDiscountCode, forceRequest, addUserNotification } = this.props

    this.setState({ discountCode: subbedCode, discountCodeIsBad: false })

    if (String(subbedCode).trim().length === 0) {
      return
    }

    let userMessage, messageType

    const resp = await applyDiscountCode(this.state.discountCode)
    if (isSuccessResponse(resp)) {
      messageType = ALERT_TYPE_SUCCESS
      userMessage = "Discount code added."

      forceRequest()
    } else {
      messageType = ALERT_TYPE_DANGER
      userMessage = `Discount code ${this.state.discountCode} is invalid.`

      this.setState({ discountCodeIsBad: true })
    }
  }

  async clearDiscount() {
    const { forceRequest, addUserNotification, clearDiscountCode } = this.props

    let userMessage, messageType

    const resp = await clearDiscountCode()

    if (isSuccessResponse(resp)) {
      messageType = ALERT_TYPE_SUCCESS
      userMessage = "Discount code cleared."

      forceRequest()
      this.setState({ discountCodeIsBad: false, discountCode: "" })
    } else {
      // TODO: this should use the banner thingy
      messageType = ALERT_TYPE_DANGER
      userMessage = `Something went wrong when trying to clear your discount code. Please contact support at ${
        SETTINGS.support_email
      }.`
    }

    addUserNotification({
      "clear-discount-notification": {
        type:  messageType,
        props: {
          text: userMessage
        }
      }
    })
  }

  renderCartItemCard(cartItem: BasketItem) {
    if (cartItem.product.purchasable_object === null) {
      return null
    }

    const purchasableObject = cartItem.product.purchasable_object
    const course = purchasableObject.course

    const title =
      course !== undefined ? (
        <a href="#" target="_blank" rel="noopener noreferrer">
          {course.title}
        </a>
      ) : (
        <a href="#" target="_blank" rel="noopener noreferrer">
          {cartItem.product.description}
        </a>
      )

    const readableId =
      course !== undefined
        ? purchasableObject.readable_id
        : purchasableObject.run_tag

    let startDate = ""
    let startDateDescription = ""

    if (purchasableObject.start_date) {
      const now = moment()
      startDate = parseDateString(purchasableObject.start_date)
      const formattedStartDate = formatPrettyDateTimeAmPmTz(startDate)
      startDateDescription = now.isBefore(startDate) ? (
        <span>Starts - {formattedStartDate}</span>
      ) : (
        <span>
          <strong>Active</strong> from {formattedStartDate}
        </span>
      )
    }

    const courseImage =
      course !== undefined && course.page !== null ? (
        <img src={course.page.feature_image_src} alt={course.title} />
      ) : null
    const cardKey = `cartsummarycard_${cartItem.id}`

    return (
      <div
        className="enrolled-item container card mb-4 rounded-0 flex-grow-1"
        key={cardKey}
      >
        <div className="row d-flex flex-sm-columm p-md-3">
          <div className="img-container">{courseImage}</div>

          <div className="flex-grow-1 d-sm-flex flex-column w-50 mx-3">
            <h5 className="">{title}</h5>
            <div className="detail">
              {readableId}
              <br />
              {startDateDescription !== undefined ? startDateDescription : ""}
            </div>
          </div>
        </div>{" "}
      </div>
    )
  }

  renderEmptyCartCard() {
    return (
      <div
        className="enrolled-item container card mb-4 rounded-0 flex-grow-1"
        key="cartsummarycard"
      >
        <div className="row d-flex flex-sm-columm p-md-3">
          <div className="flex-grow-1 mx-3 d-sm-flex flex-column">
            <div className="detail">Your cart is empty.</div>
          </div>
        </div>
      </div>
    )
  }

  renderAppliedCoupons() {
    const discounts = this.props.discounts

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
              <em className="font-weight-bold text-primary">
                {discounts[0].discount_code}
              </em>{" "}
              )
              <br />
              <a
                href="#"
                className="text-primary"
                onClick={this.clearDiscount.bind(this)}
              >
                Clear Discount
              </a>
            </div>
            <div className="ml-auto text-primary">{discountAmountText}</div>
          </div>
        </div>
      </div>
    )
  }

  renderOrderSummaryCard() {
    const {
      totalPrice,
      discountedPrice,
      discounts,
      applyDiscountCode
    } = this.props

    const fmtPrice = formatLocalePrice(totalPrice)
    const fmtDiscountPrice = formatLocalePrice(discountedPrice)

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
                <h5>{fmtDiscountPrice}</h5>
              </div>
            </div>
          </div>
        </div>

        {!SETTINGS.features.disable_discount_ui ? (
          <ApplyCouponForm
            onSubmit={this.addDiscount.bind(this)}
            discountCodeIsBad={this.state.discountCodeIsBad}
            couponCode={this.state.discountCode}
            discounts={discounts}
          />
        ) : null}

        {totalPrice > 0 ? (
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

        {totalPrice > 0 ? (
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

  render() {
    const { cartItems, isLoading } = this.props

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${CART_DISPLAY_PAGE_TITLE}`}
      >
        <Loader isLoading={isLoading}>
          <div className="std-page-body cart container">
            <div className="row">
              <div className="col-12 d-flex justify-content-between">
                <h1 className="flex-grow-1">Checkout</h1>

                <p className="text-right d-md-none">
                  <a
                    href="https://mitxonline.zendesk.com/hc/en-us"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Help &amp; FAQs
                  </a>
                </p>
              </div>
            </div>

            <div className="row d-none d-md-flex mb-3">
              <div className="col-md-8">
                <h4 className="font-weight-normal">
                  You are about to purchase the following:
                </h4>
              </div>
              <div className="col-md-4 text-right">
                <h4 className="font-weight-normal">
                  <a
                    href="https://mitxonline.zendesk.com/hc/en-us"
                    target="_blank"
                    rel="noreferrer"
                  >
                    Help &amp; FAQs
                  </a>
                </h4>
              </div>
            </div>

            <div className="row d-flex flex-column-reverse flex-md-row">
              <div className="col-md-8 enrolled-items">
                {cartItems && cartItems.length > 0
                  ? cartItems.map(this.renderCartItemCard.bind(this))
                  : this.renderEmptyCartCard()}
              </div>
              <div className="col-md-4">{this.renderOrderSummaryCard()}</div>
            </div>
          </div>
        </Loader>
      </DocumentTitle>
    )
  }
}

const applyDiscountCode = (code: string) =>
  mutateAsync(applyDiscountCodeMutation(code))

const clearDiscountCode = () => mutateAsync(clearDiscountCodeMutation())

const mapStateToProps = createStructuredSelector({
  cartItems:       cartSelector,
  totalPrice:      totalPriceSelector,
  discountedPrice: discountedPriceSelector,
  discounts:       discountSelector,
  isLoading:       () => false
})

const mapDispatchToProps = {
  addUserNotification,
  applyDiscountCode,
  clearDiscountCode
}

const mapPropsToConfig = () => [cartQuery()]

export default compose(
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(CartPage)
