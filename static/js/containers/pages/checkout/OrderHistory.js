// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import {
  ORDER_HISTORY_COLUMN_TITLES,
  ORDER_HISTORY_DISPLAY_PAGE_TITLE
} from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"
import { partial, pathOr, without } from "ramda"

import Loader from "../../../components/Loader"

import { createStructuredSelector } from "reselect"
import {
  orderHistoryQuery,
  orderHistoryQueryKey,
  orderHistorySelector
} from "../../../lib/queries/cart"

import type { RouterHistory } from "react-router"
import moment from "moment"
import {
  formatLocalePrice,
  formatPrettyDateTimeAmPmTz,
  parseDateString
} from "../../../lib/util"
import { Button } from "reactstrap"
import type { PaginatedOrderHistory } from "../../../flow/cartTypes"

type Props = {
  history: RouterHistory,
  isLoading: boolean,
  orderHistory: PaginatedOrderHistory
}

export class OrderHistory extends React.Component<Props> {
  renderOrderReceipt(orderId: number) {
    window.localStorage.setItem(
      "selectedOrderReceiptId",
      JSON.stringify(orderId)
    )
    window.location = "/orders/receipt"
  }

  renderOrderCard(order: Object) {
    const orderTitle =
      order.titles.length > 0 ? order.titles.join("<br />") : <em>No Items</em>
    const orderDate = formatPrettyDateTimeAmPmTz(
      parseDateString(order.created_on)
    )

    return (
      <div
        className="row d-flex p-3 my-0 bg-light"
        key={`ordercard_${order.id}`}
      >
        <div className="col">{orderTitle}</div>
        <div className="col">{orderDate}</div>
        <div className="col">
          {formatLocalePrice(parseFloat(order.total_price_paid))}
        </div>
        <div className="col">{order.reference_number}</div>
        <div className="col">
          <div
            className="link-text"
            onClick={() => this.renderOrderReceipt(order.id)}
          >
            View
          </div>
        </div>
      </div>
    )
  }
  render() {
    const { orderHistory, isLoading } = this.props
    const columns = ORDER_HISTORY_COLUMN_TITLES.map((value: string) => (
      <div key={value} className="col">
        <strong>{value}</strong>
      </div>
    ))
    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${ORDER_HISTORY_DISPLAY_PAGE_TITLE}`}
      >
        <Loader isLoading={isLoading}>
          <div className="std-page-body cart container">
            <div className="row">
              <div className="col-12 d-flex justify-content-between">
                <h1 className="flex-grow-1">Order History</h1>
              </div>
            </div>

            <div className="row d-flex p-3 mt-4 bg-light border-bottom border-2 border-dark">
              {columns}
            </div>
            {orderHistory && orderHistory.results.length > 0
              ? orderHistory.results.map(this.renderOrderCard.bind(this))
              : null}
            <div className="row d-flex p-3 mb-4 bg-light border-top border-2 border-dark">
              <div className="col">
                {orderHistory ? orderHistory.count : "0"} orders total
              </div>
              <div className="col text-right" />
            </div>
          </div>
        </Loader>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  orderHistory: orderHistorySelector,
  isLoading:    pathOr(true, ["queries", orderHistoryQueryKey, "isPending"])
})

const mapDispatchToProps = {}

const mapPropsToConfig = () => [orderHistoryQuery()]

export default compose(
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(OrderHistory)
