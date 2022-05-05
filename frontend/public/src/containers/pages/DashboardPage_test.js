/* global SETTINGS: false */
// @flow
import { assert } from "chai"
import moment from "moment"
import sinon from "sinon"
import { Formik } from "formik"

import DashboardPage, {
  DashboardPage as InnerDashboardPage
} from "./DashboardPage"
import { ALERT_TYPE_DANGER, ALERT_TYPE_SUCCESS } from "../../constants"
import { formatPrettyDateTimeAmPmTz } from "../../lib/util"
import { shouldIf, isIf } from "../../lib/test_utils"
import IntegrationTestHelper from "../../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../../factories/course"
import { makeUser } from "../../factories/user"
import * as courseApi from "../../lib/courseApi"

describe("DashboardPage", () => {
  let helper, renderPage, userEnrollments, currentUser, isLinkableStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]
    currentUser = makeUser()
    isLinkableStub = helper.sandbox.stub(courseApi, "isLinkableCourseRun")

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

  it("shows a message if the user has no enrollments", async () => {
    const { inner } = await renderPage({
      entities: {
        enrollments: []
      }
    })
    assert.isTrue(inner.find(".dashboard").exists())
    const enrolledItems = inner.find(".no-enrollments")
    assert.lengthOf(enrolledItems, 1)
    assert.isTrue(
      enrolledItems
        .at(0)
        .text()
        .includes("You are not enrolled in any courses yet")
    )
  })
})
