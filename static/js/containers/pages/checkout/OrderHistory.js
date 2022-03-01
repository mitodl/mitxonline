// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { ORDER_HISTORY_DISPLAY_PAGE_TITLE } from "../../../constants"
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
import { formatPrettyDateTimeAmPmTz, parseDateString } from "../../../lib/util"
import { Button } from "reactstrap"
import type { PaginatedOrderHistory } from "../../../flow/cartTypes"

type Props = {
  history: RouterHistory,
  isLoading: boolean,
  orderHistory: PaginatedOrderHistory
}

export class OrderHistory extends React.Component<Props> {
  renderOrderCard(order: Object) {
    const orderTitle =
      order.titles.length > 0 ? order.titles.join("<br />") : <em>No Items</em>
    const orderDate = formatPrettyDateTimeAmPmTz(
      parseDateString(order.created_on)
    )

    return (
      <div className="row d-flex p-3 my-0 bg-light">
        <div className="col">{orderTitle}</div>
        <div className="col">{orderDate}</div>
        <div className="col">{order.total_price_paid}</div>
        <div className="col">{order.reference_number}</div>
        <div className="col">View</div>
      </div>
    )
  }
  render() {
    const { orderHistory, isLoading } = this.props

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
              <div className="col">
                <strong>Items</strong>
              </div>
              <div className="col">
                <strong>Date placed</strong>
              </div>
              <div className="col">
                <strong>Total cost</strong>
              </div>
              <div className="col">
                <strong>Order number</strong>
              </div>
              <div className="col">
                <strong>Order details</strong>
              </div>
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
