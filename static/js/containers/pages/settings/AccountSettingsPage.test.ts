import { assert } from "chai"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { ALERT_TYPE_TEXT } from "../../../constants"
import { makeUser } from "../../../factories/user"
import * as notificationsHooks from "../../../hooks/notifications"
import { routes } from "../../../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import AccountSettingsPage from "./AccountSettingsPage"

describe("AccountSettingsPage", () => {
  const oldPassword = "password1"
  const newPassword = "password2"
  const user = makeUser()
  const email = "abc@example.com"
  const confirmPassword = newPassword

  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    setSubmittingStub: sinon.SinonStub,
    addNotificationStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    setSubmittingStub = helper.sandbox.stub()
    addNotificationStub = helper.sandbox.stub()
    helper.sandbox.stub(notificationsHooks, "useNotifications").returns({
      addNotification:     addNotificationStub,
      notifications:       {},
      dismissNotification: helper.sandbox.stub()
    })
    renderPage = helper.configureRenderer(
      AccountSettingsPage,
      {},
      {
        entities: {
          currentUser: user
        }
      }
    )
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { wrapper } = await renderPage()
    assert.ok(wrapper.find("ChangePasswordForm").exists())
  })
  ;([
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
      "Unable to reset your password, please try again later."
    ]
  ] as [number, string, string, string][]).forEach(
    ([status, expectedUrl, expectedColor, expectedMessage]) => {
      it(`handles onSubmit with status=${status}`, async () => {
        const { wrapper } = await renderPage()
        helper.handleRequestStub.returns({
          status
        })
        const onSubmit = wrapper.find("ChangePasswordForm").prop("onSubmit")
        const resetFormStub = helper.sandbox.stub()
        await act(async () => {
          await onSubmit!(
            {
              oldPassword,
              newPassword,
              confirmPassword
            },
            // @ts-ignore
            {
              setSubmitting: setSubmittingStub,
              resetForm:     resetFormStub
            }
          )
        })
        sinon.assert.calledWith(
          helper.handleRequestStub,
          "/api/set_password/",
          "POST",
          {
            body: {
              current_password: oldPassword,
              new_password:     newPassword
            },
            credentials: undefined,
            headers:     {
              "X-CSRFTOKEN": ""
            }
          }
        )
        assert.lengthOf(helper.browserHistory, 2)
        assert.include(helper.browserHistory.location, {
          pathname: expectedUrl,
          search:   ""
        })
        sinon.assert.calledWith(setSubmittingStub, false)
        sinon.assert.calledWith(resetFormStub)
        sinon.assert.calledOnceWithExactly(
          addNotificationStub,
          "password-change",
          {
            type:  ALERT_TYPE_TEXT,
            color: expectedColor,
            props: {
              text: expectedMessage
            }
          }
        )
      })
    }
  )
  ;([
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
  ] as [number, string, string, string][]).forEach(
    ([status, expectedUrl, expectedColor, expectedMessage]) => {
      it(`handles onSubmit with status=${status}`, async () => {
        const { wrapper } = await renderPage()
        const mockApi = helper.mockPostRequest(
          "/api/change-emails/",
          {},
          status
        )
        const onSubmit = wrapper.find("ChangeEmailForm").prop("onSubmit")
        const resetFormStub = helper.sandbox.stub()
        await act(async () => {
          await onSubmit!(
            {
              email,
              oldPassword,
              newPassword,
              user
            },
            // @ts-ignore
            {
              setSubmitting: setSubmittingStub,
              resetForm:     resetFormStub
            }
          )
        })
        sinon.assert.calledWith(mockApi, "/api/change-emails/", "POST", {
          body: {
            new_email: email,
            password:  undefined
          },
          credentials: undefined,
          headers:     {
            "X-CSRFTOKEN": ""
          }
        })
        assert.lengthOf(helper.browserHistory, 2)
        assert.include(helper.browserHistory.location, {
          pathname: expectedUrl,
          search:   ""
        })
        sinon.assert.calledWith(setSubmittingStub, false)
        sinon.assert.calledWith(resetFormStub)
        sinon.assert.calledOnceWithExactly(
          addNotificationStub,
          "email-change",
          {
            type:  ALERT_TYPE_TEXT,
            color: expectedColor,
            props: {
              text: expectedMessage
            }
          }
        )
      })
    }
  )
})
