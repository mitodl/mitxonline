// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { CART_DISPLAY_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"
import type { BasketItem } from "../../../flow/cartTypes"

import Loader from "../../../components/Loader"

import { createStructuredSelector } from "reselect"
import {
  cartQuery,
  cartSelector,
  totalPriceSelector
} from "../../../lib/queries/cart"

import type { RouterHistory } from "react-router"
import moment from "moment"
import { formatPrettyDateTimeAmPmTz, parseDateString } from "../../../lib/util"
import { Button } from "reactstrap"

type Props = {
  history: RouterHistory,
  cartItems: Array<BasketItem>,
  totalPrice: number,
  isLoading: boolean
}

export class CartPage extends React.Component<Props> {
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

          <div className="flex-grow-1 mx-3 d-sm-flex flex-column">
            <h5 className="mt-2">{title}</h5>
            <div className="detail">
              {readableId}
              <br />
              {startDateDescription !== undefined ? startDateDescription : ""}
            </div>
          </div>
        </div>
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

  renderOrderSummaryCard() {
    const totalPrice = this.props.totalPrice

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

        {SETTINGS.features.enable_discount_ui ? (
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
        ) : null}

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

        {SETTINGS.features.enable_discount_ui ? (
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
              <a
                href="http://mitxonline.odl.local:8013/privacy-policy/"
                target="_blank"
                rel="noreferrer"
              >
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

const mapStateToProps = createStructuredSelector({
  cartItems:  cartSelector,
  totalPrice: totalPriceSelector,
  isLoading:  () => false
})

const mapDispatchToProps = {}

const mapPropsToConfig = () => [cartQuery()]

export default compose(
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(CartPage)
