/* global SETTINGS: false */
// @flow
import { assert } from "chai"
import moment from "moment"
import sinon from "sinon"

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
  let helper,
    renderPage,
    userEnrollments,
    currentUser,
    isLinkableStub,
    isWithinEnrollmentPeriodStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]
    currentUser = makeUser()
    isLinkableStub = helper.sandbox.stub(courseApi, "isLinkableCourseRun")
    isWithinEnrollmentPeriodStub = helper.sandbox.stub(
      courseApi,
      "isWithinEnrollmentPeriod"
    )

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
    assert.equal(
      pastItemDesc.text(),
      `Active from ${formatPrettyDateTimeAmPmTz(past)}`
    )
    assert.equal(
      futureItemDesc.text(),
      `Starts - ${formatPrettyDateTimeAmPmTz(future)}`
    )
  })
  ;[[true, 204], [false, 400]].forEach(([success, returnedStatusCode]) => {
    it(`allows users to unenroll and handles ${returnedStatusCode} response`, async () => {
      window.scrollTo = sinon.stub()
      const enrollmentIndex = 0
      const enrollment = userEnrollments[enrollmentIndex]
      const expectedUserMsgProps = success
        ? {
          type: ALERT_TYPE_SUCCESS,
          msg:  `You have been successfully unenrolled from ${
            enrollment.run.title
          }.`
        }
        : {
          type: ALERT_TYPE_DANGER,
          msg:  `Something went wrong with your request to unenroll. Please contact support at ${
            SETTINGS.support_email
          }.`
        }
      isWithinEnrollmentPeriodStub.returns(true)
      helper.handleRequestStub
        .withArgs(`/api/enrollments/${enrollment.id}/`)
        .returns({
          status: returnedStatusCode
        })

      const { inner, store } = await renderPage()
      const enrolledItem = inner.find(".enrolled-item").at(enrollmentIndex)
      const unenrollBtn = enrolledItem.find("Dropdown DropdownItem").at(0)
      assert.isTrue(unenrollBtn.exists())
      await unenrollBtn.prop("onClick")()

      sinon.assert.calledWith(
        helper.handleRequestStub,
        `/api/enrollments/${enrollment.id}/`,
        "DELETE",
        {
          body:        undefined,
          credentials: undefined,
          headers:     { "X-CSRFTOKEN": null }
        }
      )
      sinon.assert.calledWith(isWithinEnrollmentPeriodStub, enrollment.run)
      assert.deepEqual(store.getState().ui.userNotifications, {
        "unenroll-status": {
          type:  expectedUserMsgProps.type,
          props: {
            text: expectedUserMsgProps.msg
          }
        }
      })
    })
  })
  ;[
    [true, "enables the unenroll button and renders no tooltip"],
    [false, "disables the unenroll button and renders tooltip"]
  ].forEach(([isEnrollable, desc]) => {
    it(`${desc} if the enrollment period ${isIf(
      isEnrollable
    )} active`, async () => {
      const enrollmentIndex = 0
      const enrollment = userEnrollments[enrollmentIndex]
      isWithinEnrollmentPeriodStub.returns(isEnrollable)

      const { inner } = await renderPage()
      const enrolledItem = inner.find(".enrolled-item").at(enrollmentIndex)
      const unenrollBtn = enrolledItem.find("Dropdown DropdownItem").at(0)
      assert.equal(
        unenrollBtn.prop("disabled"),
        isEnrollable ? undefined : true
      )
      sinon.assert.calledWith(isWithinEnrollmentPeriodStub, enrollment.run)
      const tooltip = enrolledItem.find("Tooltip")
      assert.equal(tooltip.exists(), !isEnrollable)
      if (!isEnrollable) {
        // Check that the button has a wrapper element that the tooltip can use
        const btnWrapper = unenrollBtn.parent()
        assert.equal(btnWrapper.type(), "span")
        const wrapperId = btnWrapper.prop("id")
        // Check that the tooltip correctly refers to the wrapper.
        // Our component library just requires a tooltip to refer to the id of the target element
        // in the "target" attribute, then takes care of the rest.
        assert.equal(tooltip.prop("target"), wrapperId)
      }
    })
  })
})
