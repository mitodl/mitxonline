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
import { ReceiptPageDetailCard } from "../../../components/ReceiptPageDetailCard"

import { createStructuredSelector } from "reselect"
import { orderReceiptQuery, receiptQueryKey } from "../../../lib/queries/cart"

import type { RouterHistory } from "react-router"
import type { Match } from "react-router"
import { routes } from "../../../lib/urls"
import type {
  Discount,
  Line,
  OrderReceipt,
  Refund
} from "../../../flow/cartTypes"
import { pathOr } from "ramda"

import type { PaginatedOrderHistory } from "../../../flow/cartTypes"


type Props = {
  history: RouterHistory,
  orderReceipt: OrderReceipt,
  match: Match,
  discounts: Array<Discount>,
  isLoading: boolean,
  orderHistory: PaginatedOrderHistory,
  forceRequest: () => Promise<*>
}

export class OrderReceiptPage extends React.Component<Props> {
  async componentDidMount() {
    // If we have a preloaded order but it's not the one we should display, force a fetch
    if (
      this.props.orderReceipt &&
      this.props.orderReceipt.id !== parseInt(this.props.match.params.orderId)
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
    if (!orderReceipt || !orderReceipt.total_price_paid) {
      return null
    }
    const totalPaid = parseFloat(orderReceipt.total_price_paid)
    return orderReceipt ? (
      <OrderSummaryCard
        totalPrice={totalPaid}
        discountedPrice={totalPaid}
        orderFulfilled={true}
        discounts={discounts}
        refunds={orderReceipt.refunds}
        cardTitle={`Order Number: ${orderReceipt.reference_number} `}
        discountCode=""
      />
    ) : null
  }

  renderReceiptPageDetailCard() {
    const { orderReceipt, discounts } = this.props
    if (!orderReceipt || !orderReceipt.total_price_paid) {
      return null
    }

    return (
      <ReceiptPageDetailCard
        orderReceipt={orderReceipt}
        discounts={discounts}
      />
    )
  }

  renderEmptyCartCard() {
    return (
      <div
        className="empty-card container card mb-4 rounded-0 flex-grow-1"
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
          <div className="std-page-body order-receipt container">
            <div className="enrolled-items">
              {orderReceipt &&
              orderReceipt.lines &&
              orderReceipt.lines.length > 0
                ? this.renderReceiptPageDetailCard()
                : this.renderEmptyCartCard()}
            </div>
          </div>
        </Loader>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = state => ({
  currentUser:  state.entities.currentUser,
  orderReceipt: state.entities.orderReceipt,
  discounts:    state.entities.discounts,
  isLoading:    pathOr(true, ["queries", receiptQueryKey, "isPending"], state)
})

const mapDispatchToProps = {}

const mapPropsToConfig = props => [
  orderReceiptQuery(props.match.params.orderId)
]

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(OrderReceiptPage)
