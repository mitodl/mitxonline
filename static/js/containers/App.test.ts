import sinon from "sinon"
import * as notificationsHooks from "../hooks/notifications"
import * as notificationsApi from "../lib/notificationsApi"
import { routes } from "../lib/urls"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import App from "./App"

describe("Top-level App", () => {
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    getStoredUserMessageStub: sinon.SinonStub,
    removeStoredUserMessageStub: sinon.SinonStub,
    getCurrentUserStub: sinon.SinonStub,
    addNotificationStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    getStoredUserMessageStub = helper.sandbox
      .stub(notificationsApi, "getStoredUserMessage")
      .returns(null)
    removeStoredUserMessageStub = helper.sandbox.stub(
      notificationsApi,
      "removeStoredUserMessage"
    )
    addNotificationStub = helper.sandbox.stub()
    helper.sandbox.stub(notificationsHooks, "useNotifications").returns({
      addNotification:     addNotificationStub,
      notifications:       {},
      dismissNotification: helper.sandbox.stub()
    })
    getCurrentUserStub = helper.mockGetRequest("/api/users/me", {})
    helper.browserHistory.push(routes.root)
    renderPage = helper.configureRenderer(App)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("fetches user data on load", async () => {
    await renderPage()
    sinon.assert.calledOnce(getCurrentUserStub)
  })

  it("adds a user notification if a stored message is found in cookies", async () => {
    const userMsg = {
      type: "some-type",
      text: "some text"
    }
    getStoredUserMessageStub.returns(userMsg)
    await renderPage()
    sinon.assert.calledOnceWithExactly(addNotificationStub, "loaded-user-msg", {
      type:  userMsg.type,
      props: {
        text: userMsg.text
      }
    })
    sinon.assert.calledOnce(removeStoredUserMessageStub)
  })
})
