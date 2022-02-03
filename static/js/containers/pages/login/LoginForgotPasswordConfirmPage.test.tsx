import { assert } from "chai"
import { reverse } from "named-urls"
import React from "react"
import { act } from "react-dom/test-utils"
import { Route } from "react-router"
import sinon from "sinon"
import { ALERT_TYPE_TEXT } from "../../../constants"
import * as notificationsHooks from "../../../hooks/notifications"
import { routes } from "../../../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import LoginForgotPasswordConfirmPage from "./LoginForgotPasswordConfirmPage"

const RoutedPage = () => (
  <Route
    path={routes.login.forgot.confirm}
    component={LoginForgotPasswordConfirmPage}
  />
)

describe("LoginForgotPasswordConfirmPage", () => {
  const newPassword = "pass1"
  const confirmPassword = "pass2"
  const token = "token1"
  const uid = "uid1"

  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    setSubmittingStub: sinon.SinonStub,
    resetConfirmApiStub: sinon.SinonStub,
    addNotificationStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    setSubmittingStub = helper.sandbox.stub()
    resetConfirmApiStub = helper.mockPostRequest(
      "/api/password_reset/confirm/",
      {}
    )
    addNotificationStub = helper.sandbox.stub()
    helper.sandbox.stub(notificationsHooks, "useNotifications").returns({
      addNotification:     addNotificationStub,
      notifications:       {},
      dismissNotification: helper.sandbox.stub()
    })
    helper.browserHistory.push(
      reverse(routes.login.forgot.confirm, {
        uid,
        token
      })
    )
    renderPage = helper.configureRenderer(RoutedPage)
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { wrapper } = await renderPage()
    assert.ok(wrapper.find("ResetPasswordForm").exists())
  })
  ;([
    [
      200,
      routes.login.begin,
      "Your password has been updated, you may use it to sign in now."
    ],
    [
      400,
      routes.login.forgot.begin,
      "Unable to reset your password with that link, please try again."
    ]
  ] as [number, string, string][]).forEach(
    ([status, expectedUrl, expectedMessage]) => {
      it(`handles onSubmit with status=${status}`, async () => {
        const { wrapper } = await renderPage()
        resetConfirmApiStub.returns({
          status
        })
        const onSubmit = wrapper.find("ResetPasswordForm").prop("onSubmit")
        await act(async () => {
          await onSubmit!(
            {
              newPassword,
              confirmPassword
            },
            // @ts-ignore
            {
              setSubmitting: setSubmittingStub
            }
          )
        })
        sinon.assert.calledWith(
          resetConfirmApiStub,
          "/api/password_reset/confirm/",
          "POST",
          {
            body: {
              new_password:    newPassword,
              re_new_password: confirmPassword,
              token,
              uid
            },
            credentials: undefined,
            headers:     {
              "X-CSRFTOKEN": ""
            }
          }
        )
        assert.lengthOf(helper.browserHistory, 3)
        assert.include(helper.browserHistory.location, {
          pathname: expectedUrl,
          search:   ""
        })
        sinon.assert.calledWith(setSubmittingStub, false)
        sinon.assert.calledOnceWithExactly(
          addNotificationStub,
          "forgot-password-confirm",
          {
            type:  ALERT_TYPE_TEXT,
            props: {
              text: expectedMessage
            }
          }
        )
      })
    }
  )
})
