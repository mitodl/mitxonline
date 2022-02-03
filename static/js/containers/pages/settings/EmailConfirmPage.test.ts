import sinon from "sinon"
import { makeUser } from "../../../factories/user"
import * as notificationsHooks from "../../../hooks/notifications"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import EmailConfirmPage from "./EmailConfirmPage"

describe("EmailConfirmPage", () => {
  const user = makeUser()
  const code = "email-confirm-code"
  let helper: IntegrationTestHelper,
    render: TestRenderer,
    addNotificationStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    helper.browserHistory.push(`/?verification_code=${code}`)
    addNotificationStub = helper.sandbox.stub()
    helper.sandbox.stub(notificationsHooks, "useNotifications").returns({
      addNotification:     addNotificationStub,
      notifications:       {},
      dismissNotification: helper.sandbox.stub()
    })
    helper.mockGetRequest("/api/users/me", user)
    render = helper.configureActRenderer(
      EmailConfirmPage,
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

  it("shows a message when the confirmation page is displayed", async () => {
    helper.mockPatchRequest(`/api/change-emails/${code}/`, { confirmed: true })

    await render()

    sinon.assert.calledOnceWithExactly(addNotificationStub, "email-verified", {
      type:  "text",
      props: {
        text: "Success! We've verified your email. Your email has been updated."
      }
    })
  })

  it("shows a message when the error page is displayed", async () => {
    helper.mockPatchRequest(`/api/change-emails/${code}/`, { confirmed: false })
    await render()
    sinon.assert.calledOnceWithExactly(addNotificationStub, "email-verified", {
      type:  "text",
      color: "danger",
      props: {
        text: "Error! No confirmation code was provided or it has expired."
      }
    })
  })
})
