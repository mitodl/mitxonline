// @flow
import { assert } from "chai"
import sinon from "sinon"

import DashboardPage, {
  DashboardPage as InnerDashboardPage
} from "./DashboardPage"

import IntegrationTestHelper from "../../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../../factories/course"
import { makeAnonymousUser, makeUser } from "../../factories/user"
import * as util from "../../lib/util"

describe("DashboardPage", () => {
  let helper, renderPage, userEnrollments, currentUser, sandbox, mockSettings

  beforeEach(() => {
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
      mit_learn_dashboard_url: undefined
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
    const FLAG = "redirect-to-learn-dashboard"
    const DEFAULT_DASHBOARD_URL = "https://learn.mit.edu/dashboard"

    let mockLocation, checkFeatureFlagStub, clock

    beforeEach(() => {
      mockLocation = { href: "", search: "" }
      sandbox.stub(window, "location").value(mockLocation)

      checkFeatureFlagStub = sandbox.stub(util, "checkFeatureFlag")

      // The component defers its flag check with setTimeout
      clock = sandbox.useFakeTimers()
    })

    afterEach(() => {
      // Reset mit_learn_dashboard_url to undefined for subsequent tests
      mockSettings.mit_learn_dashboard_url = undefined
    })

    const renderForUser = (mockUser: Object) =>
      renderPage(
        { entities: { enrollments: userEnrollments, currentUser: mockUser } },
        { currentUser: mockUser }
      )

    it("redirects to the default dashboard URL when the flag is enabled", async () => {
      const mockUser = makeUser()
      checkFeatureFlagStub.withArgs(FLAG, mockUser.global_id).returns(true)

      await renderForUser(mockUser)

      sinon.assert.notCalled(checkFeatureFlagStub)

      clock.tick(500)

      sinon.assert.calledWith(checkFeatureFlagStub, FLAG, mockUser.global_id)
      assert.equal(mockLocation.href, DEFAULT_DASHBOARD_URL)
    })

    it("preserves query parameters in the redirect URL", async () => {
      const mockUser = makeUser()
      mockLocation.search = "?a=1&b=2"
      checkFeatureFlagStub.withArgs(FLAG, mockUser.global_id).returns(true)

      await renderForUser(mockUser)
      clock.tick(500)

      assert.equal(mockLocation.href, `${DEFAULT_DASHBOARD_URL}?a=1&b=2`)
    })

    it("uses MIT_LEARN_DASHBOARD_URL when it is set", async () => {
      const mockUser = makeUser()
      const customDashboardUrl = "https://custom.example.com/dashboard"
      mockSettings.mit_learn_dashboard_url = customDashboardUrl
      checkFeatureFlagStub.withArgs(FLAG, mockUser.global_id).returns(true)

      await renderForUser(mockUser)
      clock.tick(500)

      assert.equal(mockLocation.href, customDashboardUrl)
    })

    it("does not redirect when the flag is disabled", async () => {
      const mockUser = makeUser()
      checkFeatureFlagStub.withArgs(FLAG, mockUser.global_id).returns(false)

      await renderForUser(mockUser)
      clock.tick(500)

      sinon.assert.calledWith(checkFeatureFlagStub, FLAG, mockUser.global_id)
      assert.equal(mockLocation.href, "")
    })

    it("does not redirect when the flag check throws", async () => {
      const mockUser = makeUser()
      checkFeatureFlagStub
        .withArgs(FLAG, mockUser.global_id)
        .throws(new Error("PostHog service unavailable"))

      await renderForUser(mockUser)
      clock.tick(500)

      sinon.assert.calledWith(checkFeatureFlagStub, FLAG, mockUser.global_id)
      assert.equal(mockLocation.href, "")
    })

    it("does not check the flag when the user has no global_id", async () => {
      await renderForUser({ ...makeUser(), global_id: null })
      clock.tick(500)

      sinon.assert.notCalled(checkFeatureFlagStub)
      assert.equal(mockLocation.href, "")
    })

    it("does not check the flag when there is no current user", async () => {
      await renderPage(
        {
          entities: {
            enrollments: userEnrollments,
            currentUser: makeAnonymousUser()
          }
        },
        { currentUser: null }
      )
      clock.tick(500)

      sinon.assert.notCalled(checkFeatureFlagStub)
      assert.equal(mockLocation.href, "")
    })

    it("does not check the flag when PostHog is not configured", async () => {
      global.SETTINGS.posthog_api_host = null

      await renderForUser(makeUser())
      clock.tick(500)

      sinon.assert.notCalled(checkFeatureFlagStub)
      assert.equal(mockLocation.href, "")
    })
  })
})
