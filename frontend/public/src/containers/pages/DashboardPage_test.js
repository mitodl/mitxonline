// @flow
import { assert } from "chai"


import DashboardPage, {
  DashboardPage as InnerDashboardPage
} from "./DashboardPage"

import IntegrationTestHelper from "../../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../../factories/course"
import { makeUser } from "../../factories/user"

describe("DashboardPage", () => {
  let helper, renderPage, userEnrollments, currentUser

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]
    currentUser = makeUser()

    renderPage = helper.configureHOCRenderer(
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
  })

  it("renders a dashboard", async () => {
    const { inner } = await renderPage()
    assert.isTrue(inner.find(".dashboard").exists())
  })
})
