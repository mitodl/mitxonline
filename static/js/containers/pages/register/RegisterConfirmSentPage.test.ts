/* global SETTINGS: false */
import { assert } from "chai"
import { routes } from "../../../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import RegisterConfirmSentPage from "./RegisterConfirmSentPage"

describe("RegisterConfirmSentPage", () => {
  const userEmail = "test@example.com"
  const supportEmail = "email@localhost"

  let helper: IntegrationTestHelper, renderPage: TestRenderer

  beforeEach(() => {
    SETTINGS.support_email = supportEmail
    helper = new IntegrationTestHelper()
    helper.browserHistory.push(`/?email=${encodeURIComponent(userEmail)}`)
    renderPage = helper.configureRenderer(RegisterConfirmSentPage)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("displays a link to email support", async () => {
    const { wrapper } = await renderPage()
    assert.equal(
      wrapper.find(".contact-support > a").prop("href"),
      `mailto:${supportEmail}`
    )
  })

  it("displays a link to create account page", async () => {
    const { wrapper } = await renderPage()
    assert.equal(wrapper.find("Link").at(0).prop("to"), routes.register.begin)
  })

  it("displays user's email on the page", async () => {
    const { wrapper } = await renderPage()
    assert.include(wrapper.find(".auth-card").text(), userEmail)
  })
})
