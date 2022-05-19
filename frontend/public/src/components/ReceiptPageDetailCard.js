// @flow
/* global SETTINGS: false */
import React from "react"
import {
    parseDateString,
    formatPrettyDate,
} from "../lib/util"

export class ReceiptPageDetailCard extends React.Component<Props> {    
    render() {
        const { orderReceipt, discounts } = this.props
        const totalPaid = parseFloat(orderReceipt.total_price_paid)
        let orderDate = null
        let stateCode = null
        let countryName = null

        if (orderReceipt) {
            orderDate = parseDateString(orderReceipt.created_on)
        }

        return (
            <div className="receipt-wrapper">
                <div className="receipt-row p-b-80">
                    <div className="receipt-col">
                        <div className="receipt-logo">
                            <img src="static/images/mitx-online-logo.png" alt="" />
                        </div>
                        <div className="receipt-mit-info">
                            <p>
                            600 Technology Square
                            <br />
                            NE49-2000
                            <br />
                            Cambridge, MA 02139 USA
                            <br />
                            Support:{" "}
                            <a href="mailto:support@mitxonline.mit.edu">
                                support@mit.edu
                            </a>
                            <br />
                            <a
                                target="_blank"
                                href="https://mitxonline.mit.edu/"
                                rel="noreferrer"
                            >
                                mitxonline.mit.edu
                            </a>
                            </p>
                        </div>
                    </div>
                    <div className="receipt-col p-t-50">
                        <dl>
                            <dt>Order Number:</dt>
                            <dd id="orderNumber">
                            {orderReceipt.reference_number}
                            </dd>
                        </dl>
                        <dl>
                            <dt>Order Date:</dt>
                            {orderDate ? (
                            <dd id="orderDate">{formatPrettyDate(orderDate)}</dd>
                            ) : null}
                        </dl>
                        <a href="javascript:window.print();" className="print-btn">
                            <img src="static/images/printer.png" alt="print" />
                        </a>
                    </div>
                </div>
                <h2>Receipt</h2>
                <div className="receipt-row p-b-80">
                  <div className="receipt-col">
                    <h3>Customer Information</h3>
                    <dl>
                      <dt>Name:</dt>
                      <dd id="purchaserName">
                        {orderReceipt.purchaser.first_name}{" "}
                        {orderReceipt.purchaser.last_name}
                      </dd>
                    </dl>
                    <dl>
                      <dt>Address:</dt>
                      <dd>
                        {orderReceipt.street_address.line.map(_line => (
                          <div
                            className="value low-line-height"
                            key={_line}
                            id={_line}
                          >
                            {_line}
                          </div>
                        ))}
                        <div
                          className="value low-line-height"
                          id="purchaserState"
                        >
                          {orderReceipt.street_address.city}, {stateCode}{" "}
                          {orderReceipt.street_address.postal_code}
                        </div>
                        <div
                          className="value low-line-height"
                          id="purchaserCountry"
                        >
                          {orderReceipt.street_address.country}
                        </div>
                      </dd>
                    </dl>
                    <dl>
                      <dt>Email:</dt>
                      <dd id="purchaserEmail">
                        {orderReceipt.purchaser.email}
                      </dd>
                    </dl>
                  </div>
                  <h3>Payment Information</h3>
                  {orderReceipt.transactions ? (
                    <div className="receipt-col">
                      {orderReceipt.transactions &&
                      orderReceipt.transactions.payment_method === "card" ? (
                          <div>
                            <dl>
                              <dt>Name:</dt>
                              <dd>{orderReceipt.transactions.name}</dd>
                            </dl>
                            <dl>
                              <dt>Payment Method:</dt>
                              <dd id="paymentMethod">
                                {orderReceipt.transactions.card_type
                                  ? `${orderReceipt.transactions.card_type} | `
                                  : null}
                                {orderReceipt.transactions.card_number
                                  ? orderReceipt.transactions.card_number
                                  : null}
                              </dd>
                            </dl>
                          </div>
                        ) : orderReceipt.transactions.payment_method === "paypal" ? (
                          <div>
                            <dl>
                              {orderReceipt.transactions.bill_to_email ? (
                                <dl>
                                  <dt>Email:</dt>
                                  <dd>{orderReceipt.transactions.bill_to_email}</dd>
                                </dl>
                              ) : null}
                            </dl>
                            <dl>
                              <dt>Payment Method:</dt>
                              <dd id="paymentMethod">Paypal</dd>
                            </dl>
                          </div>
                        ) : null}
                    </div>
                  ) : null}
                </div>
                <div className="receipt-table-holder">
                  <h3>Product Description</h3>
                  <table className="receipt-table">
                    <thead>
                      <tr>
                        <th>Product Description</th>
                        <th>Quantity</th>
                        <th>Unit Price</th>
                        {discounts.length ? (
                            <th>Discount</th>
                        ) : null }
                        <th>Total Paid</th>
                      </tr>
                    </thead>
                    <tbody>
                      {orderReceipt.lines.map(line => {
                        const startDate = parseDateString(line.product.purchasable_object.start_date)
                        const endDate = parseDateString(line.product.purchasable_object.end_date)
                        return (
                          <tr key={line.product.purchasable_object.readable_id}>
                            <td>
                              <div>
                                {line.product.purchasable_object.title} <br />
                                {line.product.purchasable_object.readable_id} <br />
                                {startDate &&
                                  formatPrettyDate(startDate)} -{" "}
                                {endDate && formatPrettyDate(endDate)}
                              </div>
                            </td>
                            <td>
                              <div>{line.quantity}</div>
                            </td>
                            <td>
                              <div>${line.product.price}</div>
                            </td>
                            {discounts.length ? (
                                <td>
                                    <div>${discounts}</div>
                                </td>
                            ) : null }
                            <td>
                              <div>${totalPaid}</div>
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>
            </div>
        )
    }
}
