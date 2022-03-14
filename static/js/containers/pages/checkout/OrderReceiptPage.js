// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { ORDER_RECEIPT_DISPLAY_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"

import Loader from "../../../components/Loader"
import { CartItemCard } from "../../../components/CartItemCard"
import { OrderSummaryCard } from "../../../components/OrderSummaryCard"

import { createStructuredSelector } from "reselect"
import {
  discountSelector,
  orderReceiptQuery,
  orderReceiptSelector
} from "../../../lib/queries/cart"

import type { RouterHistory } from "react-router"
import type { Match } from "react-router"
import { routes } from "../../../lib/urls"
import type { Discount, Line, OrderReceipt } from "../../../flow/cartTypes"

type Props = {
  history: RouterHistory,
  orderReceipt: OrderReceipt,
  discounts: Array<Discount>,
  match: Match,
  isLoading: boolean,
  forceRequest: () => Promise<*>
}

export class OrderReceiptPage extends React.Component<Props> {
  async componentDidMount() {
    // If we have a preloaded order but it's not the one we should display, force a fetch
    if (
      this.props.orderReceipt &&
      this.props.orderReceipt.id !==
        parseInt(this.props.match.params.orderId)
    ) {
      await this.props.forceRequest()
    }
  }

  async componentDidUpdate(prevProps: Props) {
    if (prevProps.match.params.orderId !== this.props.match.params.orderId) {
      await this.props.forceRequest()
    }
  }
  renderCartItemCard(orderItem: Line) {
    return (
      <CartItemCard
        key={`itemcard_${orderItem.product.id}`}
        product={orderItem.product}
      />
    )
  }

  renderOrderSummaryCard() {
    const { orderReceipt, discounts } = this.props
    if (!orderReceipt) {
      return null
    }
    const totalPaid = parseFloat(orderReceipt.total_price_paid)
    return orderReceipt ? (
      <OrderSummaryCard
        totalPrice={totalPaid}
        discountedPrice={totalPaid}
        orderFulfilled={true}
        discounts={discounts}
        cardTitle={`Order Number: ${orderReceipt.reference_number} `}
        discountCodeIsBad={false}
      />
    ) : null
  }
  renderEmptyCartCard() {
    return (
      <div
        className="enrolled-item container card mb-4 rounded-0 flex-grow-1"
        key="emptycard"
      >
        <div className="row d-flex flex-sm-columm p-md-3">
          <div className="flex-grow-1 mx-3 d-sm-flex flex-column">
            <div className="detail">
              There was an error retrieving your order.
            </div>
          </div>
        </div>
      </div>
    )
  }

  render() {
    const { orderReceipt, isLoading } = this.props
    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${ORDER_RECEIPT_DISPLAY_PAGE_TITLE}`}
      >
        <Loader isLoading={isLoading}>
          <div className="std-page-body cart container">
            <div className="row">
              <div className="col-8 d-flex justify-content-between">
                <h1 className="flex-grow-1">Order Receipt</h1>
              </div>
              <div className="col-md-4 text-right align-middle">
                <p className="font-weight-normal mt-3">
                  <a
                    href={routes.orderHistory}
                    className="link-text align-middle"
                  >
                    Back to Order History
                  </a>
                </p>
              </div>
            </div>

            <div className="row d-flex flex-column-reverse flex-md-row">
              <div className="col-md-8 enrolled-items">
                {orderReceipt &&
                orderReceipt.lines &&
                orderReceipt.lines.length > 0
                  ? orderReceipt.lines.map(this.renderCartItemCard.bind(this))
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
  orderReceipt: orderReceiptSelector,
  discounts:    discountSelector,
  isLoading:    () => false
})

const mapDispatchToProps = {}

const mapPropsToConfig = props => [
  orderReceiptQuery(props.match.params.orderId)
]

export default compose(
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(OrderReceiptPage)
