import sinon from "sinon"
import * as notificationsHooks from "../../../hooks/notifications"
import {
  STATE_EXISTING_ACCOUNT,
  STATE_INVALID_EMAIL,
  STATE_INVALID_LINK,
  STATE_REGISTER_DETAILS
} from "../../../lib/auth"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import RegisterConfirmPage from "./RegisterConfirmPage"

describe("RegisterConfirmPage", () => {
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    addNotificationStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    addNotificationStub = helper.sandbox.stub()
    helper.sandbox.stub(notificationsHooks, "useNotifications").returns({
      addNotification:     addNotificationStub,
      notifications:       {},
      dismissNotification: helper.sandbox.stub()
    })
    renderPage = helper.configureRenderer(RegisterConfirmPage)
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("shows a message when the confirmation page is displayed and redirects", async () => {
    helper.handleRequestStub.returns({})
    const token = "asdf"
    await renderPage({}, [], {
      entities: {
        auth: {
          state:         STATE_REGISTER_DETAILS,
          partial_token: token,
          extra_data:    {
            name: "name"
          }
        }
      }
    })
    sinon.assert.calledOnceWithExactly(addNotificationStub, "email-verified", {
      type:  "text",
      props: {
        text:
          "Success! We've verified your email. Please finish your account creation below."
      }
    })
    expect(helper.currentLocation).toMatchObject({
      pathname: "/create-account/details/",
      search:   `?partial_token=${token}`
    })
  })

  it("Shows a register link with invalid/expired confirmation code", async () => {
    helper.handleRequestStub.returns({})
    const token = "asdf"
    const { wrapper } = await renderPage({}, [], {
      entities: {
        auth: {
          state:         STATE_INVALID_LINK,
          partial_token: token,
          extra_data:    {}
        }
      }
    })
    const confirmationErrorText = wrapper.find(".confirmation-message")
    expect(confirmationErrorText).not.toBeNull()
    expect(confirmationErrorText.text()).toEqual(
      "This invitation is invalid or has expired. Please click here to register again."
    )
  })

  it("Shows a login link with existing account message", async () => {
    helper.handleRequestStub.returns({})
    const token = "asdf"
    const { wrapper } = await renderPage({}, [], {
      entities: {
        auth: {
          state:         STATE_EXISTING_ACCOUNT,
          partial_token: token,
          extra_data:    {}
        }
      }
    })
    const confirmationErrorText = wrapper.find(".confirmation-message")
    expect(confirmationErrorText).not.toBeNull()
    expect(confirmationErrorText.text()).toEqual(
      "You already have an mitX Online account. Please click here to sign in."
    )
  })

  it("Shows a register link with invalid or no confirmation code", async () => {
    helper.mockPostRequest("/api/register/confirm/", {
      state:         STATE_INVALID_EMAIL,
      partial_token: "asdf",
      extra_data:    {}
    })
    const { wrapper } = await renderPage()
    const confirmationErrorText = wrapper.find(".confirmation-message")
    expect(confirmationErrorText.text()).toEqual(
      "No confirmation code was provided or it has expired. Please click here to register again."
    )
  })
})
