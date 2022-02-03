import { assert } from "chai"
import { FormikConfig } from "formik"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { ALERT_TYPE_TEXT } from "../../../constants"
import { makeRegisterAuthResponse } from "../../../factories/auth"
import * as notificationsHooks from "../../../hooks/notifications"
import {
  STATE_ERROR,
  STATE_LOGIN_PASSWORD,
  STATE_REGISTER_CONFIRM_SENT,
  STATE_REGISTER_EMAIL
} from "../../../lib/auth"
import { routes } from "../../../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import RegisterEmailPage from "./RegisterEmailPage"

describe("RegisterEmailPage", () => {
  const email = "email@example.com"
  const recaptcha = "recaptchaTestValue"
  const partialToken = "partialTokenTestValue"
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    setSubmittingStub: sinon.SinonStub,
    setErrorsStub: sinon.SinonStub,
    addNotificationStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    setSubmittingStub = helper.sandbox.stub()
    setErrorsStub = helper.sandbox.stub()
    addNotificationStub = helper.sandbox.stub()
    helper.sandbox.stub(notificationsHooks, "useNotifications").returns({
      addNotification:     addNotificationStub,
      notifications:       {},
      dismissNotification: helper.sandbox.stub()
    })
    helper.browserHistory.push(`partial_token=${partialToken}`)
    renderPage = helper.configureRenderer(RegisterEmailPage)
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { wrapper } = await renderPage()
    assert.ok(wrapper.find("RegisterEmailForm").exists())
  })

  it("handles onSubmit for an error response", async () => {
    const { wrapper } = await renderPage()
    const fieldErrors = {
      email: "error message"
    }
    helper.handleRequestStub.returns({
      body: makeRegisterAuthResponse({
        state:        STATE_ERROR,
        field_errors: fieldErrors
      })
    })
    const onSubmit = wrapper
      .find("RegisterEmailForm")
      .prop("onSubmit") as FormikConfig<any>["onSubmit"]
    await act(async () => {
      await onSubmit!(
        {
          email,
          recaptcha
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub,
          setErrors:     setErrorsStub
        }
      )
    })
    assert.lengthOf(helper.browserHistory, 2)
    sinon.assert.calledWith(setErrorsStub, fieldErrors)
    sinon.assert.calledWith(setSubmittingStub, false)
  })

  it("handles onSubmit for an existing user password login", async () => {
    const { wrapper } = await renderPage()
    helper.mockPostRequest(
      "/api/register/email/",
      makeRegisterAuthResponse({
        state: STATE_LOGIN_PASSWORD
      })
    )
    const onSubmit = wrapper.find("RegisterEmailForm").prop("onSubmit")
    await act(async () => {
      await onSubmit!(
        {
          email,
          recaptcha
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub,
          setErrors:     setErrorsStub
        }
      )
    })
    assert.lengthOf(helper.browserHistory, 3)
    assert.include(helper.browserHistory.location, {
      pathname: routes.login.password,
      search:   ""
    })
    sinon.assert.notCalled(setErrorsStub)
    sinon.assert.calledWith(setSubmittingStub, false)
    sinon.assert.calledOnceWithExactly(addNotificationStub, "account-exists", {
      type:  ALERT_TYPE_TEXT,
      color: "danger",
      props: {
        text: `You already have an account with ${email}. Enter password to sign in.`
      }
    })
  })

  it("handles onSubmit for blocked email", async () => {
    const { wrapper } = await renderPage()
    helper.mockPostRequest(
      "/api/register/email/",
      makeRegisterAuthResponse({
        state: STATE_REGISTER_EMAIL
      })
    )
    const onSubmit = wrapper.find("RegisterEmailForm").prop("onSubmit")
    await act(async () => {
      await onSubmit!(
        {
          email,
          recaptcha
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub,
          setErrors:     setErrorsStub
        }
      )
    })
    sinon.assert.notCalled(setErrorsStub)
    sinon.assert.calledWith(setSubmittingStub, false)
    sinon.assert.calledOnceWithMatch(addNotificationStub, "account-blocked", {
      type:  ALERT_TYPE_TEXT,
      color: "danger",
      props: {
        text: sinon.match.any
      }
    })
  })

  it("handles onSubmit for a confirmation email", async () => {
    const { wrapper } = await renderPage()
    helper.handleRequestStub.returns({
      body: makeRegisterAuthResponse({
        state: STATE_REGISTER_CONFIRM_SENT
      })
    })
    const onSubmit = wrapper.find("RegisterEmailForm").prop("onSubmit")

    await act(async () => {
      await onSubmit!(
        {
          email,
          recaptcha
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub,
          setErrors:     setErrorsStub
        }
      )
    })

    assert.lengthOf(helper.browserHistory, 3)
    assert.include(helper.browserHistory.location, {
      pathname: routes.register.confirmSent,
      search:   `?email=${encodeURIComponent(email)}`
    })
    sinon.assert.notCalled(setErrorsStub)
    sinon.assert.calledWith(setSubmittingStub, false)
  })
})
