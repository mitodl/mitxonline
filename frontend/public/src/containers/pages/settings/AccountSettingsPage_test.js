// @flow
/* global SETTINGS: false */
import { assert } from "chai"
import sinon from "sinon"

import AccountSettingsPage, {
  AccountSettingsPage as InnerAccountSettingsPage
} from "./AccountSettingsPage"
import IntegrationTestHelper from "../../../util/integration_test_helper"
import { routes } from "../../../lib/urls"
import { ALERT_TYPE_TEXT } from "../../../constants"
import { makeUser } from "../../../factories/user"

describe("AccountSettingsPage", () => {
  const currentPassword = "password1"
  const newPassword = "password2"
  const user = makeUser()
  const email = "abc@example.com"
  const confirmPasswordChangePassword = newPassword

  let helper, renderPage, setSubmittingStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    setSubmittingStub = helper.sandbox.stub()

    renderPage = helper.configureShallowRenderer(
      AccountSettingsPage,
      InnerAccountSettingsPage,
      {},
      {}
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { inner } = await renderPage()

    assert.ok(inner.find("ChangePasswordForm").exists())
  })
  ;[
    [
      200,
      routes.accountSettings,
      "success",
      "Your password has been updated successfully."
    ],

    [
      400,
      routes.accountSettings,
      "danger",
      "Unable to update your password, please try again later."
    ]
  ].forEach(([status, expectedUrl, expectedColor, expectedMessage]) => {
    it(`handles onSubmit with status=${status}`, async () => {
      const { inner, store } = await renderPage()

      helper.handleRequestStub.returns({
        status
      })

      const onSubmit = inner.find("ChangePasswordForm").prop("onSubmit")

      const changePasswordFormStub = helper.sandbox.stub()

      await onSubmit(
        { currentPassword, newPassword, confirmPasswordChangePassword },
        { setSubmitting: setSubmittingStub, resetForm: changePasswordFormStub }
      )
      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/set_password/",
        "POST",
        {
          body: {
            current_password: currentPassword,
            new_password:     newPassword
          },
          credentials: undefined,
          headers:     { "X-CSRFTOKEN": null }
        }
      )

      assert.lengthOf(helper.browserHistory, 2)
      assert.include(helper.browserHistory.location, {
        pathname: expectedUrl,
        search:   ""
      })
      sinon.assert.calledWith(setSubmittingStub, false)
      sinon.assert.calledWith(changePasswordFormStub)

      const { ui } = store.getState()
      assert.deepEqual(ui.userNotifications, {
        "password-change": {
          type:  ALERT_TYPE_TEXT,
          color: expectedColor,
          props: {
            text: expectedMessage
          }
        }
      })
    })
  })

  //
  ;[
    [
      200,
      routes.accountSettings,
      "success",
      "You have been sent a verification email on your updated address. Please click on the link in the email to finish email address update."
    ],

    [
      400,
      routes.accountSettings,
      "danger",
      "Unable to update your email address, please try again later."
    ]
  ].forEach(([status, expectedUrl, expectedColor, expectedMessage]) => {
    it(`handles onSubmit with status=${status}`, async () => {
      const { inner, store } = await renderPage({
        entities: {
          currentUser: user
        }
      })

      helper.handleRequestStub.returns({
        status
      })

      const onSubmit = inner.find("ChangeEmailForm").prop("onSubmit")

      const resetFormStub = helper.sandbox.stub()

      await onSubmit(
        { email, confirmPasswordChangePassword, newPassword, user },
        { setSubmitting: setSubmittingStub, resetForm: resetFormStub }
      )
      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/change-emails/",
        "POST",
        {
          body: {
            new_email: email,
            password:  undefined
          },
          credentials: undefined,
          headers:     { "X-CSRFTOKEN": null }
        }
      )

      assert.lengthOf(helper.browserHistory, 2)
      assert.include(helper.browserHistory.location, {
        pathname: expectedUrl,
        search:   ""
      })
      sinon.assert.calledWith(setSubmittingStub, false)
      sinon.assert.calledWith(resetFormStub)

      const { ui } = store.getState()
      assert.deepEqual(ui.userNotifications, {
        "email-change": {
          type:  ALERT_TYPE_TEXT,
          color: expectedColor,
          props: {
            text: expectedMessage
          }
        }
      })
    })
  })

  it("Displays buttons to update email/password if api gateway is enabled", async () => {
    SETTINGS.api_gateway_enabled = true
    const { inner } = await renderPage({
      entities: {
        currentUser: user
      }
    })
    assert.isFalse(inner.find("ChangeEmailForm").exists())
    assert.isFalse(inner.find("ChangePasswordForm").exists())

    const changeEmailBtn = inner.find("a[aria-label='change email']")

    assert.ok(changeEmailBtn.exists())
    assert.equal(
      changeEmailBtn.prop("href"),
      "/account/action/start/update-email/"
    )

    const changePasswordBtn = inner.find("a[aria-label='change password']")

    assert.ok(changePasswordBtn.exists())
    assert.equal(
      changePasswordBtn.prop("href"),
      "/account/action/start/update-password/"
    )
  })
})
