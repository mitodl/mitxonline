/* global SETTINGS: false */
// @flow
import { assert } from "chai"
import moment from "moment"

import DashboardPage, {
  DashboardPage as InnerDashboardPage
} from "./DashboardPage"
import { formatPrettyDateTimeAmPmTz } from "../../lib/util"
import { shouldIf, isIf } from "../../lib/test_utils"
import IntegrationTestHelper from "../../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../../factories/course"
import { makeUser } from "../../factories/user"
import * as courseApi from "../../lib/courseApi"

describe("DashboardPage", () => {
  let helper, isLinkableStub, renderPage, userEnrollments, currentUser

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
    const enrolledItems = inner.find(".enrolled-item")
    assert.lengthOf(enrolledItems, userEnrollments.length)
    userEnrollments.forEach((userEnrollment, i) => {
      const enrolledItem = enrolledItems.at(i)
      assert.equal(
        enrolledItem.find("h2").text(),
        userEnrollment.run.course.title
      )
    })
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
  ;[[false, false], [true, true]].forEach(([isLinkable, expCourseLink]) => {
    it(`${shouldIf(expCourseLink)} show a link if course run ${isIf(
      isLinkable
    )} linkable`, async () => {
      isLinkableStub.returns(isLinkable)
      const exampleCoursewareUrl = "http://example.com/my-course"
      userEnrollments[0].run.courseware_url = exampleCoursewareUrl
      const enrollment = {
        ...userEnrollments[0]
      }
      const { inner } = await renderPage({
        entities: { enrollments: [enrollment] }
      })
      const enrolledItems = inner.find(".enrolled-item")
      assert.lengthOf(enrolledItems, 1)
      assert.equal(
        enrolledItems
          .at(0)
          .find("a")
          .exists(),
        expCourseLink
      )
      if (expCourseLink) {
        const linkedTitle = enrolledItems.at(0).find("h2")
        assert.equal(linkedTitle.find("a").prop("href"), exampleCoursewareUrl)
      }
    })
  })

  it("shows different text depending on whether the start date is in the future or past", async () => {
    const past = moment().add(-1, "days"),
      future = moment().add(1, "days")
    userEnrollments[0].run.start_date = past.toISOString()
    userEnrollments[1].run.start_date = future.toISOString()
    const { inner } = await renderPage({
      entities: { enrollments: userEnrollments }
    })
    const enrolledItems = inner.find(".enrolled-item")
    const pastItemDesc = enrolledItems.at(0).find(".detail")
    const futureItemDesc = enrolledItems.at(1).find(".detail")
    assert.equal(pastItemDesc.text(), `Active from ${formatPrettyDateTimeAmPmTz(past)}`)
    assert.equal(futureItemDesc.text(), `Starts - ${formatPrettyDateTimeAmPmTz(future)}`)
  })
})
