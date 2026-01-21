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
    if (!global.performance) {
      global.performance = {}
    }

    const mockFn = () => undefined

    ;["mark", "measure", "clearMarks", "clearMeasures"].forEach(method => {
      try {
        if (typeof global.performance[method] !== "function") {
          Object.defineProperty(global.performance, method, {
            value:        mockFn,
            writable:     true,
            configurable: true
          })
        }
      } catch (e) {
        try {
          global.performance[method] = mockFn
        } catch (err) {
          // If all else fails, silently skip - the mock may already exist
        }
      }
    })

    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]
    currentUser = {
      id:               1,
      email:            "default@test.com",
      name:             "Default User",
      is_anonymous:     false,
      is_authenticated: true
      // No global_id by default
    }
    sandbox = sinon.createSandbox()

    // Mock SETTINGS global
    mockSettings = {
      posthog_api_host:        "https://app.posthog.com",
      environment:             "test",
      site_name:               "Test Site",
      MIT_LEARN_DASHBOARD_URL: undefined
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
    let mockLocation, posthogIdentifyStub, checkFeatureFlagStub, clock

    beforeEach(() => {
      // Mock window.location.href
      mockLocation = { href: "" }
      sandbox.stub(window, "location").value(mockLocation)

      // Mock PostHog methods
      posthogIdentifyStub = sandbox.stub(posthog, "identify")

      // Mock checkFeatureFlag
      checkFeatureFlagStub = sandbox.stub(util, "checkFeatureFlag")

      // Create fake timer to control setTimeout
      clock = sandbox.useFakeTimers()
    })

    afterEach(() => {
      // Reset mit_learn_dashboard_url to undefined for subsequent tests
      mockSettings.mit_learn_dashboard_url = undefined
    })

    it("identifies user to PostHog and redirects when feature flag is enabled", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Mock checkFeatureFlag to return true
      checkFeatureFlagStub
        .withArgs("redirect-to-learn-dashboard", "test-guid-123")
        .returns(true)

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Component mounts automatically, so PostHog calls should have been made
      // Check that PostHog identify was called
      sinon.assert.called(posthogIdentifyStub)

      // Check the identify call had the correct GUID
      const identifyCall = posthogIdentifyStub.getCall(0)
      assert.equal(identifyCall.args[0], "test-guid-123")
      assert.equal(identifyCall.args[1].email, mockUser.email)
      assert.equal(identifyCall.args[1].name, mockUser.name)
      assert.equal(identifyCall.args[1].user_id, mockUser.id)
      assert.equal(identifyCall.args[1].environment, "test")

      // Feature flag check hasn't happened yet (it's in setTimeout)
      sinon.assert.notCalled(checkFeatureFlagStub)

      // Advance time to trigger the setTimeout
      clock.tick(500)

      // Now verify checkFeatureFlag was called
      sinon.assert.calledWith(
        checkFeatureFlagStub,
        "redirect-to-learn-dashboard",
        "test-guid-123"
      )

      // Verify redirect happened
      assert.equal(mockLocation.href, "https://learn.mit.edu/dashboard")
    })

    it("does not redirect when feature flag is disabled", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Mock checkFeatureFlag to return false
      checkFeatureFlagStub
        .withArgs("redirect-to-learn-dashboard", "test-guid-123")
        .returns(false)

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Component mounts automatically, so PostHog calls should have been made
      // Verify PostHog identify was called
      sinon.assert.called(posthogIdentifyStub)

      // Feature flag check hasn't happened yet (it's in setTimeout)
      sinon.assert.notCalled(checkFeatureFlagStub)

      // Advance time to trigger the setTimeout
      clock.tick(500)

      // Now verify checkFeatureFlag was called
      sinon.assert.calledWith(
        checkFeatureFlagStub,
        "redirect-to-learn-dashboard",
        "test-guid-123"
      )

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })

    it("does not redirect when user has no global_id", async () => {
      const mockUser = {
        id:               123,
        email:            "test@example.com",
        name:             "Test User",
        is_anonymous:     false,
        is_authenticated: true
        // Explicitly no global_id property
      }

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Component mounts automatically
      // Since there's no global_id, PostHog identify should not be called
      sinon.assert.notCalled(posthogIdentifyStub)

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })

    it("does not redirect when PostHog is not configured", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-123"

      // Remove PostHog configuration
      global.SETTINGS.posthog_api_host = null

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Component mounts automatically
      // Verify PostHog identify was not called
      sinon.assert.notCalled(posthogIdentifyStub)

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })

    it("handles checkFeatureFlag returning true", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-456"

      // Mock checkFeatureFlag to return true
      checkFeatureFlagStub
        .withArgs("redirect-to-learn-dashboard", "test-guid-456")
        .returns(true)

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Verify PostHog identify was called
      sinon.assert.called(posthogIdentifyStub)

      // Feature flag check hasn't happened yet (it's in setTimeout)
      sinon.assert.notCalled(checkFeatureFlagStub)

      // Advance time to trigger the setTimeout
      clock.tick(500)

      // Now verify checkFeatureFlag was called
      sinon.assert.calledWith(
        checkFeatureFlagStub,
        "redirect-to-learn-dashboard",
        "test-guid-456"
      )

      // Verify redirect happened
      assert.equal(mockLocation.href, "https://learn.mit.edu/dashboard")
    })

    it("handles checkFeatureFlag gracefully when it throws an error", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-789"

      // Mock checkFeatureFlag to throw an error
      checkFeatureFlagStub
        .withArgs("redirect-to-learn-dashboard", "test-guid-789")
        .throws(new Error("PostHog service unavailable"))

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Verify PostHog identify was called
      sinon.assert.called(posthogIdentifyStub)

      // Feature flag check hasn't happened yet (it's in setTimeout)
      sinon.assert.notCalled(checkFeatureFlagStub)

      // Advance time to trigger the setTimeout
      clock.tick(500)

      // Now verify checkFeatureFlag was called
      sinon.assert.calledWith(
        checkFeatureFlagStub,
        "redirect-to-learn-dashboard",
        "test-guid-789"
      )

      // Verify no redirect happened (error handled gracefully)
      assert.equal(mockLocation.href, "")
    })

    it("handles undefined currentUser gracefully", async () => {
      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: {
              // Minimal user object that won't break the component
              id:               null,
              is_anonymous:     true,
              is_authenticated: false
            }
          }
        },
        { currentUser: null }
      )

      // Component mounts automatically with null user
      // Since there's no currentUser, PostHog identify should not be called
      sinon.assert.notCalled(posthogIdentifyStub)

      // Verify no redirect happened
      assert.equal(mockLocation.href, "")
    })

    it("uses MIT_LEARN_DASHBOARD_URL setting when provided", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-custom-url"

      // Set custom URL in settings - this needs to be a truthy value
      const customDashboardUrl = "https://custom.example.com/dashboard"
      mockSettings.mit_learn_dashboard_url = customDashboardUrl

      // Mock checkFeatureFlag to return true
      checkFeatureFlagStub
        .withArgs("redirect-to-learn-dashboard", "test-guid-custom-url")
        .returns(true)

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Component mounts automatically
      // Verify PostHog identify was called
      sinon.assert.called(posthogIdentifyStub)

      // Feature flag check hasn't happened yet (it's in setTimeout)
      sinon.assert.notCalled(checkFeatureFlagStub)

      // Advance time to trigger the setTimeout
      clock.tick(500)

      // Now verify checkFeatureFlag was called
      sinon.assert.calledWith(
        checkFeatureFlagStub,
        "redirect-to-learn-dashboard",
        "test-guid-custom-url"
      )

      // Verify redirect happened with custom URL
      assert.equal(mockLocation.href, customDashboardUrl)
    })

    it("falls back to default URL when MIT_LEARN_DASHBOARD_URL is not set", async () => {
      const mockUser = makeUser()
      mockUser.global_id = "test-guid-fallback"

      // Ensure MIT_LEARN_DASHBOARD_URL is explicitly not set
      mockSettings.MIT_LEARN_DASHBOARD_URL = undefined

      // Mock checkFeatureFlag to return true
      checkFeatureFlagStub
        .withArgs("redirect-to-learn-dashboard", "test-guid-fallback")
        .returns(true)

      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: mockUser // Override the currentUser from beforeEach
          }
        },
        { currentUser: mockUser }
      )

      // Component mounts automatically
      // Verify PostHog identify was called
      sinon.assert.called(posthogIdentifyStub)

      // Feature flag check hasn't happened yet (it's in setTimeout)
      sinon.assert.notCalled(checkFeatureFlagStub)

      // Advance time to trigger the setTimeout
      clock.tick(500)

      // Now verify checkFeatureFlag was called
      sinon.assert.calledWith(
        checkFeatureFlagStub,
        "redirect-to-learn-dashboard",
        "test-guid-fallback"
      )

      // Verify redirect happened with default URL (fallback)
      assert.equal(mockLocation.href, "https://learn.mit.edu/dashboard")
    })
  })
})
