import sinon from "sinon"
import * as notificationsHooks from "../hooks/notifications"
import * as notificationsApi from "../lib/notificationsApi"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import HeaderApp from "./HeaderApp"

describe("Top-level HeaderApp", () => {
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    getStoredUserMessageStub: sinon.SinonStub,
    removeStoredUserMessageStub: sinon.SinonStub,
    addNotificationStub: sinon.SinonStub,
    getCurrentUserStub: sinon.SinonStub

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
    renderPage = helper.configureRenderer(HeaderApp)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("fetches user data on load", async () => {
    await renderPage()
    sinon.assert.calledWith(getCurrentUserStub, "/api/users/me", "GET")
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
