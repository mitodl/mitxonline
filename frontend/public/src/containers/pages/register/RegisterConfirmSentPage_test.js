// @flow
/* global SETTINGS: false */
import { assert } from "chai"

import RegisterConfirmSentPage, {
  RegisterConfirmSentPage as InnerRegisterConfirmSentPage
} from "./RegisterConfirmSentPage"
import IntegrationTestHelper from "../../../util/integration_test_helper"

import { routes } from "../../../lib/urls"

describe("RegisterConfirmSentPage", () => {
  const userEmail = "test@example.com"
  const supportEmail = "email@localhost"

  let helper, renderPage

  beforeEach(() => {
    SETTINGS.support_email = supportEmail

    helper = new IntegrationTestHelper()

    renderPage = helper.configureShallowRenderer(
      RegisterConfirmSentPage,
      InnerRegisterConfirmSentPage,
      {},
      {
        location: {
          search: `?email=${encodeURIComponent(userEmail)}`
        }
      }
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("displays a link to email support", async () => {
    const { inner } = await renderPage()
    assert.equal(
      inner.find("a.support-email").prop("href"),
      `mailto:${supportEmail}`
    )
  })

  it("displays a link to create account page", async () => {
    const { inner } = await renderPage()
    assert.equal(
      inner
        .find("Link")
        .at(0)
        .prop("to"),
      routes.register.begin
    )
  })

  it("displays user's email on the page", async () => {
    const { inner } = await renderPage()
    assert.include(inner.find(".std-card-body").text(), userEmail)
  })
})
