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
import { connectRequest, mutateAsync } from "redux-query"
import { pathOr } from "ramda"

import Loader from "../../../components/Loader"

import { createStructuredSelector } from "reselect"
import {
  orderHistoryQuery,
  orderHistoryQueryKey,
  orderHistorySelector
} from "../../../lib/queries/cart"

import type { RouterHistory } from "react-router"
import {
  formatLocalePrice,
  formatPrettyDateTimeAmPmTz,
  parseDateString
} from "../../../lib/util"
import type { PaginatedOrderHistory } from "../../../flow/cartTypes"

type Props = {
  history: RouterHistory,
  isLoading: boolean,
  orderHistory: PaginatedOrderHistory,
  updateOrderHistory: Function
}

export class OrderHistory extends React.Component<Props> {
  offset = 0

  async swapPage(direction: string) {
    const { updateOrderHistory } = this.props

    switch (direction) {
    case "previous":
      if (this.offset <= 0) {
        this.offset = 0
      } else {
        this.offset--
      }
      break

    case "next":
      if (this.offset * 10 < this.props.orderHistory.count) {
        this.offset++
      }

      break

    default:
      break
    }

    await updateOrderHistory(this.offset * 10)
  }

  renderOrderReceipt(orderReference: string) {
    window.location = `/orders/receipt/${orderReference}/`
  }

  renderOrderCard(order: Object) {
    const orderTitle =
      order.titles.length > 0 ? order.titles.join("<br />") : <em>No Items</em>
    const orderDate = formatPrettyDateTimeAmPmTz(
      parseDateString(order.created_on)
    )
    return (
      <tr scope="row" key={`ordercard_${order.id}`}>
        <th className="d-flex">
          <span className="flex-grow-1">{orderTitle}</span>
        </th>
        <td>{orderDate}</td>
        <td>{formatLocalePrice(parseFloat(order.total_price_paid))}</td>
        <td>{order.reference_number}</td>
        <td>
          <a
            className="link-text"
            aria-label={`View order details for ${order.titles}`}
            onClick={() => this.renderOrderReceipt(order.id)}
            href="#"
            role="link"
          >
            View
          </a>
        </td>
      </tr>
    )
  }

  renderMobileOrderCard(order: Object) {
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

  renderPaginationNext() {
    const { orderHistory } = this.props

    return orderHistory && orderHistory.next !== null ? (
      <a
        className="history-paginators"
        href="#"
        onClick={() => this.swapPage("next")}
      >
        Next
      </a>
    ) : (
      "Next"
    )
  }

  renderPaginationPrevious() {
    const { orderHistory } = this.props

    return orderHistory && orderHistory.previous !== null ? (
      <a
        className="history-paginators"
        href="#"
        onClick={() => this.swapPage("previous")}
      >
        Previous
      </a>
    ) : (
      "Previous"
    )
  }

  render() {
    const { orderHistory, isLoading } = this.props
    const columns = ORDER_HISTORY_COLUMN_TITLES.map((value: string) => (
      <th key={value} scope="col">
        <strong>{value}</strong>
      </th>
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
            <div className="d-md-none">
              <div className="row d-flex p-3 mt-4 bg-light border-bottom border-2 border-dark">
                {ORDER_HISTORY_COLUMN_TITLES.map((value: string) => (
                  <div key={value} className="col">
                    <strong>{value}</strong>
                  </div>
                ))}
              </div>
              {orderHistory && orderHistory.results.length > 0
                ? orderHistory.results.map(
                  this.renderMobileOrderCard.bind(this)
                )
                : null}
            </div>
            <div className="d-none d-md-block">
              <div className="row">
                <div className="col-12 d-flex bg-light justify-content-between">
                  <table title="Order History" className="order-history-table">
                    <thead className="border-bottom border-2 border-dark">
                      <tr>{columns}</tr>
                    </thead>
                    <tbody>
                      {orderHistory && orderHistory.results.length > 0
                        ? orderHistory.results.map(
                          this.renderOrderCard.bind(this)
                        )
                        : null}
                      <tr className="border-top border-2 border-dark">
                        <td>
                          Page {this.offset + 1} of{" "}
                          {orderHistory
                            ? Math.ceil(orderHistory.count / 10)
                            : 0}{" "}
                          | {orderHistory ? orderHistory.count : "0"} orders
                          total
                        </td>
                        <td />
                        <td />
                        <td />
                        <td className="col text-right">
                          {this.renderPaginationPrevious()} |{" "}
                          {this.renderPaginationNext()}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          </div>
        </Loader>
      </DocumentTitle>
    )
  }
}

const updateOrderHistory = (offset: number = 0) => {
  return mutateAsync(orderHistoryQuery(offset))
}

const mapStateToProps = createStructuredSelector({
  orderHistory: orderHistorySelector,
  isLoading:    pathOr(true, ["queries", orderHistoryQueryKey, "isPending"])
})

const mapDispatchToProps = {
  updateOrderHistory
}

const mapPropsToConfig = () => [orderHistoryQuery()]

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(OrderHistory)
