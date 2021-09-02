/* global SETTINGS: false */
// @flow
import { assert } from "chai"
import moment from "moment"

import DashboardPage, {
  DashboardPage as InnerDashboardPage
} from "./DashboardPage"
import { formatPrettyDate } from "../../lib/util"
import { shouldIf } from "../../lib/test_utils"
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
          enrollments: userEnrollments
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
        enrolledItem.find("h4").text(),
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
    const enrolledItems = inner.find(".enrolled-item")
    assert.lengthOf(enrolledItems, 1)
    assert.equal(
      enrolledItems.at(0).text(),
      "Once you enroll in a course, you can find it listed here."
    )
  })

  it("links to the courseware URL if that property is set on the course run", async () => {
    const past = moment().add(-10, "days"),
      future = moment().add(10, "days")
    const exampleCoursewareUrl = "http://example.com/my-course"
    userEnrollments[0].run.courseware_url = exampleCoursewareUrl
    userEnrollments[0].run.start_date = past.toISOString()
    userEnrollments[0].run.end_date = future.toISOString()
    userEnrollments[1].run.courseware_url = null
    const { inner } = await renderPage({
      entities: { enrollments: userEnrollments }
    })
    const enrolledItems = inner.find(".enrolled-item")
    assert.lengthOf(enrolledItems, userEnrollments.length)
    const linkedTitle = enrolledItems.at(0).find("h4")
    const unlinkedTitle = enrolledItems.at(1).find("h4")
    assert.isTrue(linkedTitle.find("a").exists())
    assert.equal(linkedTitle.find("a").prop("href"), exampleCoursewareUrl)
    assert.isFalse(unlinkedTitle.find("a").exists())
  })

  it("Not links to the courseware URL if run is started in future", async () => {
    const future = moment().add(10, "days")
    const exampleCoursewareUrl = "http://example.com/my-course"
    userEnrollments[0].run.courseware_url = exampleCoursewareUrl
    userEnrollments[0].run.start_date = future.toISOString()
    userEnrollments[0].run.end_date = future.toISOString()
    const { inner } = await renderPage({
      entities: { enrollments: userEnrollments }
    })
    const enrolledItems = inner.find(".enrolled-item")
    assert.lengthOf(enrolledItems, userEnrollments.length)
    const unlinkedTitle = enrolledItems.at(0).find("h4")
    assert.isFalse(unlinkedTitle.find("a").exists())
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
    assert.equal(pastItemDesc.text(), `Active from ${formatPrettyDate(past)}`)
    assert.equal(futureItemDesc.text(), `Starts - ${formatPrettyDate(future)}`)
  })
})
