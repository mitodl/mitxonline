// @flow
import React from "react"
import { shallow } from "enzyme"
import { assert } from "chai"

import { ReceiptPageDetailCard } from "./ReceiptPageDetailCard"
import { ORDER_RECEIPT_OBJECT } from "../lib/test_constants"

describe("ReceiptPageDetailCard", () => {
  const line = {
    start_date:    null,
    end_date:      null,
    readable_id:   "course-v1:MITx+1+1T2026",
    content_title: "A course",
    price:         100,
    total_paid:    100,
    quantity:      1
  }

  const render = (lines, taxes) =>
    shallow(
      <ReceiptPageDetailCard
        orderReceipt={{ ...ORDER_RECEIPT_OBJECT, lines, taxes }}
        discounts={[]}
      />
    )

  it("shows a tax column, named for the tax, and a total including it", () => {
    const wrapper = render(
      [{ ...line, tax_paid: "18.00" }],
      [{ tax_rate_name: "VAT", rate: "18.0000", tax_amount: "18.00" }]
    )

    const headers = wrapper.find("th").map(th => th.text())
    assert.include(headers, "VAT")
    const cells = wrapper.find("tbody td").map(td => td.text())
    assert.include(cells, "$18.00")
    assert.include(cells, "$118.00")
  })

  it("shows no tax column for an untaxed order", () => {
    const wrapper = render([{ ...line, tax_paid: "0.00" }], [])

    const headers = wrapper.find("th").map(th => th.text())
    assert.notInclude(headers, "Tax")
    assert.notInclude(headers, "VAT")
    const cells = wrapper.find("tbody td").map(td => td.text())
    assert.include(cells, "$100")
  })
})
