// @flow
import { assert } from "chai"
import sinon from "sinon"
import posthog from "posthog-js"

import DashboardPage, {
  DashboardPage as InnerDashboardPage
} from "./DashboardPage"

import IntegrationTestHelper from "../../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../../factories/course"
import { makeUser } from "../../factories/user"
import * as util from "../../lib/util"

describe("DashboardPage", () => {
  let helper, renderPage, userEnrollments, currentUser, sandbox, mockSettings

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]
    currentUser = makeUser()
    sandbox = sinon.createSandbox()

    // Mock SETTINGS global
    mockSettings = {
      posthog_api_host: "https://app.posthog.com",
      environment:      "test",
      site_name:        "Test Site"
    }
    global.SETTINGS = mockSettings

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
    delete global.SETTINGS
  })

  it("renders a dashboard", async () => {
    const { inner } = await renderPage()
    assert.isTrue(inner.find(".dashboard").exists())
  })

  describe("PostHog feature flag redirect", () => {
    let mockLocation,
      posthogIdentifyStub,
      posthogOnFeatureFlagsStub,
      posthogIsFeatureEnabledStub

    beforeEach(() => {
      // Mock window.location.href
      mockLocation = { href: "" }
      sandbox.stub(window, "location").value(mockLocation)

      // Mock PostHog methods
      posthogIdentifyStub = sandbox.stub(posthog, "identify")
      posthogOnFeatureFlagsStub = sandbox.stub(posthog, "onFeatureFlags")
      posthogIsFeatureEnabledStub = sandbox.stub(posthog, "isFeatureEnabled")
    })

    it("identifies user to PostHog and redirects when feature flag is enabled", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Mock PostHog feature flag to return true
      posthogIsFeatureEnabledStub
        .withArgs("redirect-to-learn-dashboard")
        .returns(true)

      // Mock onFeatureFlags to immediately call the callback
      posthogOnFeatureFlagsStub.callsFake(callback => {
        callback()
      })

      const { inner } = await renderPage({}, { currentUser: mockUser })

      // Trigger componentDidMount
      inner.instance().componentDidMount()

      // Verify PostHog identify was called with correct parameters
      sinon.assert.calledWith(posthogIdentifyStub, mockUser.global_id, {
        email:       mockUser.email,
        name:        mockUser.name,
        user_id:     mockUser.id,
        environment: "test"
      })

      // Verify onFeatureFlags was called
      sinon.assert.calledOnce(posthogOnFeatureFlagsStub)

      // Verify redirect happened
      assert.equal(mockLocation.href, "https://learn.mit.edu/dashboard")
    })

    it("does not redirect when feature flag is disabled", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Mock PostHog feature flag to return false
      posthogIsFeatureEnabledStub
        .withArgs("redirect-to-learn-dashboard")
        .returns(false)

      // Mock onFeatureFlags to immediately call the callback
      posthogOnFeatureFlagsStub.callsFake(callback => {
        callback()
      })

      // Mock checkFeatureFlag to return false as well
      sandbox
        .stub(util, "checkFeatureFlag")
        .withArgs("redirect-to-learn-dashboard", mockUser.global_id)
        .returns(false)

      const { inner } = await renderPage({}, { currentUser: mockUser })

      // Trigger componentDidMount
      inner.instance().componentDidMount()

      // Verify PostHog identify was called
      sinon.assert.calledOnce(posthogIdentifyStub)

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })

    it("does not redirect when user has no global_id", async () => {
      const mockUser = makeUser()
      mockUser.global_id = null

      const { inner } = await renderPage({}, { currentUser: mockUser })

      // Trigger componentDidMount
      inner.instance().componentDidMount()

      // Verify PostHog identify was not called
      sinon.assert.notCalled(posthogIdentifyStub)

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })

    it("does not redirect when PostHog is not configured", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Remove PostHog configuration
      global.SETTINGS.posthog_api_host = null

      const { inner } = await renderPage({}, { currentUser: mockUser })

      // Trigger componentDidMount
      inner.instance().componentDidMount()

      // Verify PostHog identify was not called
      sinon.assert.notCalled(posthogIdentifyStub)

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })

    it("falls back to checkFeatureFlag when onFeatureFlags callback doesn't trigger", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Mock PostHog methods to return false initially
      posthogIsFeatureEnabledStub
        .withArgs("redirect-to-learn-dashboard")
        .returns(false)

      // Mock onFeatureFlags to not call the callback (simulating it not triggering)
      posthogOnFeatureFlagsStub.callsFake(() => {})

      // Mock checkFeatureFlag to return true (fallback should work)
      sandbox
        .stub(util, "checkFeatureFlag")
        .withArgs("redirect-to-learn-dashboard", mockUser.global_id)
        .returns(true)

      // Mock setTimeout to immediately call the callback
      sandbox.stub(window, "setTimeout").callsFake(callback => {
        callback()
      })

      const { inner } = await renderPage({}, { currentUser: mockUser })

      // Trigger componentDidMount
      inner.instance().componentDidMount()

      // Verify PostHog identify was called
      sinon.assert.calledOnce(posthogIdentifyStub)

      // Verify redirect happened via fallback
      assert.equal(mockLocation.href, "https://learn.mit.edu/dashboard")
    })

    it("redirects via fallback when direct PostHog check returns true", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Mock onFeatureFlags to not call the callback
      posthogOnFeatureFlagsStub.callsFake(() => {})

      // Mock checkFeatureFlag to return false but direct PostHog check to return true
      sandbox
        .stub(util, "checkFeatureFlag")
        .withArgs("redirect-to-learn-dashboard", mockUser.global_id)
        .returns(false)
      posthogIsFeatureEnabledStub
        .withArgs("redirect-to-learn-dashboard")
        .returns(true)

      // Mock setTimeout to immediately call the callback
      sandbox.stub(window, "setTimeout").callsFake(callback => {
        callback()
      })

      const { inner } = await renderPage({}, { currentUser: mockUser })

      // Trigger componentDidMount
      inner.instance().componentDidMount()

      // Verify redirect happened via direct PostHog check
      assert.equal(mockLocation.href, "https://learn.mit.edu/dashboard")
    })

    it("handles undefined currentUser gracefully", async () => {
      const { inner } = await renderPage({}, { currentUser: null })

      // Trigger componentDidMount
      inner.instance().componentDidMount()

      // Verify no PostHog calls were made
      sinon.assert.notCalled(posthogIdentifyStub)

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })
  })
})
