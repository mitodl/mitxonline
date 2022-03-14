// @flow
import { assert } from "chai"

import OrderReceiptPage, {
  OrderReceiptPage as InnerOrderReceiptPage
} from "./OrderReceiptPage"
import { makeUser } from "../../../factories/user"
import IntegrationTestHelper from "../../../util/integration_test_helper"
import * as courseApi from "../../../lib/courseApi"
import { ORDER_RECEIPT_OBJECT } from "../../../lib/test_constants"

describe("OrderReceiptPage", () => {
  let helper, renderPage, currentUser, isLinkableStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    isLinkableStub = helper.sandbox.stub(courseApi, "isLinkableCourseRun")

    renderPage = helper.configureHOCRenderer(
      OrderReceiptPage,
      InnerOrderReceiptPage,
      {
        entities: {
          orderReceipt: ORDER_RECEIPT_OBJECT,
          currentUser:  currentUser
        },
        queries: {
          orderReceipt: {
            isPending: false
          }
        }
      },
      {
        match: {
          params: {
            orderId: 1
          }
        }
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })
  it("renders the page with a receipt for a logged in user", async () => {
    const { inner } = await renderPage()
    assert.isTrue(inner.find(".order-receipt").exists())
    assert.equal(inner.find(".back-link").text(), "Back to Order History")
  })
})
