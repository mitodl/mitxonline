/* global SETTINGS: false */
import { assert } from "chai"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { routes } from "../../../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import LoginForgotPasswordPage from "./LoginForgotPasswordPage"

describe("LoginForgotPasswordPage", () => {
  const email = "email@example.com"
  const supportEmail = "email@localhost"
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    setSubmittingStub: sinon.SinonStub,
    apiStub: sinon.SinonStub

  beforeEach(() => {
    SETTINGS.support_email = supportEmail
    helper = new IntegrationTestHelper()
    setSubmittingStub = helper.sandbox.stub()
    apiStub = helper.mockPostRequest("/api/password_reset/", {})
    renderPage = helper.configureRenderer(LoginForgotPasswordPage)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { wrapper } = await renderPage()
    assert.ok(wrapper.find("EmailForm").exists())
  })

  it("handles onSubmit", async () => {
    const { wrapper } = await renderPage()
    const onSubmit = wrapper.find("EmailForm").prop("onSubmit")
    await act(async () => {
      await onSubmit!(
        {
          email
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub
        }
      )
    })
    sinon.assert.calledWith(apiStub, "/api/password_reset/", "POST", {
      body: {
        email
      },
      credentials: undefined,
      headers:     {
        "X-CSRFTOKEN": ""
      }
    })
    sinon.assert.calledWith(setSubmittingStub, false)
  })

  it("after submit it remains on the forgot password page", async () => {
    const { wrapper } = await renderPage()
    const onSubmit = wrapper.find("EmailForm").prop("onSubmit")
    await act(async () => {
      await onSubmit!(
        {
          email
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub
        }
      )

      wrapper.update()
    })
    assert.isNotTrue(wrapper.find("EmailForm").exists())
  })

  it("contains the customer support link", async () => {
    const { wrapper } = await renderPage()
    const onSubmit = wrapper.find("EmailForm").prop("onSubmit")
    await act(async () => {
      await onSubmit!(
        {
          email
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub
        }
      )

      wrapper.update()
    })
    assert.equal(
      wrapper.find(".contact-support > a").prop("href"),
      `mailto:${supportEmail}`
    )
  })

  it("contains the reset your password link", async () => {
    const { wrapper } = await renderPage()
    const onSubmit = wrapper.find("EmailForm").prop("onSubmit")
    await act(async () => {
      await onSubmit!(
        {
          email
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub
        }
      )

      wrapper.update()
    })
    assert.equal(
      wrapper.find("li > Link").prop("to"),
      routes.login.forgot.begin
    )
  })
})
