// @flow
import { assert } from "chai"
import sinon from "sinon"

import DashboardPage, {
  DashboardPage as InnerDashboardPage
} from "./DashboardPage"

import IntegrationTestHelper from "../../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../../factories/course"
import { makeUser } from "../../factories/user"
import * as util from "../../lib/util"

describe("DashboardPage", () => {
  let helper, renderPage, userEnrollments, currentUser, sandbox

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]
    currentUser = makeUser()
    sandbox = sinon.createSandbox()

    renderPage = helper.configureShallowRenderer(
      DashboardPage,
      InnerDashboardPage,
      {
        entities: {
          enrollments: userEnrollments,
          currentUser: currentUser
        }
      },
      {}
    )
  })

  afterEach(() => {
    helper.cleanup()
    sandbox.restore()
  })

  it("renders a dashboard", async () => {
    const { inner } = await renderPage()
    assert.isTrue(inner.find(".dashboard").exists())
  })

  it("redirects to learn.mit.edu/dashboard when feature flag is enabled", async () => {
    const mockUser = makeUser()
    mockUser.global_id = "test-guid-123"
    
    // Mock the feature flag check to return true
    sandbox.stub(util, "checkFeatureFlag").withArgs("redirect-to-learn-dashboard", mockUser.global_id).returns(true)
    
    // Mock window.location.href
    const mockLocation = { href: "" }
    sandbox.stub(window, "location").value(mockLocation)

    const { inner } = await renderPage({}, { currentUser: mockUser })
    
    // componentDidMount should trigger the redirect
    inner.instance().componentDidMount()
    
    assert.equal(mockLocation.href, "https://learn.mit.edu/dashboard")
  })

  it("does not redirect when feature flag is disabled", async () => {
    const mockUser = makeUser()
    mockUser.global_id = "test-guid-123"
    
    // Mock the feature flag check to return false
    sandbox.stub(util, "checkFeatureFlag").withArgs("redirect-to-learn-dashboard", mockUser.global_id).returns(false)
    
    // Mock window.location.href
    const mockLocation = { href: "" }
    sandbox.stub(window, "location").value(mockLocation)

    const { inner } = await renderPage({}, { currentUser: mockUser })
    
    // componentDidMount should not trigger the redirect
    inner.instance().componentDidMount()
    
    assert.equal(mockLocation.href, "")
  })

  it("does not redirect when user has no global_id", async () => {
    const mockUser = makeUser()
    mockUser.global_id = null
    
    // Mock window.location.href
    const mockLocation = { href: "" }
    sandbox.stub(window, "location").value(mockLocation)

    const { inner } = await renderPage({}, { currentUser: mockUser })
    
    // componentDidMount should not trigger the redirect
    inner.instance().componentDidMount()
    
    assert.equal(mockLocation.href, "")
  })
})
