import { assert } from "chai"
import moment from "moment"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { ALERT_TYPE_DANGER, ALERT_TYPE_SUCCESS } from "../../constants"
import { makeCourseRunEnrollment } from "../../factories/course"
import { makeUser } from "../../factories/user"
import * as notificationsHooks from "../../hooks/notifications"
import * as courseApi from "../../lib/courseApi"
import { isIf, shouldIf } from "../../lib/test_utils"
import { formatPrettyDateTimeAmPmTz } from "../../lib/util"
import { LoggedInUser } from "../../types/auth"
import { RunEnrollment } from "../../types/course"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import DashboardPage from "./DashboardPage"

describe("DashboardPage", () => {
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    userEnrollments: RunEnrollment[],
    currentUser: LoggedInUser,
    isLinkableStub: sinon.SinonStub,
    isWithinEnrollmentPeriodStub: sinon.SinonStub,
    addNotificationStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollments = [makeCourseRunEnrollment(), makeCourseRunEnrollment()]
    currentUser = makeUser()
    isLinkableStub = helper.sandbox.stub(courseApi, "isLinkableCourseRun")
    isWithinEnrollmentPeriodStub = helper.sandbox
      .stub(courseApi, "isWithinEnrollmentPeriod")
      .returns(false)
    addNotificationStub = helper.sandbox.stub()
    helper.sandbox.stub(notificationsHooks, "useNotifications").returns({
      addNotification:     addNotificationStub,
      notifications:       {},
      dismissNotification: helper.sandbox.stub()
    })
    helper.mockGetRequest("/api/enrollments/", userEnrollments)
    helper.mockGetRequest("/api/user/me", currentUser)
    renderPage = helper.configureRenderer(DashboardPage)
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders a dashboard", async () => {
    const { wrapper } = await renderPage()
    assert.isTrue(wrapper.find(".dashboard").exists())
    const enrolledItems = wrapper.find(".enrolled-item")
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
    helper.mockGetRequest("/api/enrollments/", [])
    const { wrapper } = await renderPage()
    assert.isTrue(wrapper.find(".dashboard").exists())
    const enrolledItems = wrapper.find(".no-enrollments")
    assert.lengthOf(enrolledItems, 1)
    assert.isTrue(
      enrolledItems
        .at(0)
        .text()
        .includes("You are not enrolled in any courses yet")
    )
  })
  ;[
    [false, false],
    [true, true]
  ].forEach(([isLinkable, expCourseLink]) => {
    it(`${shouldIf(expCourseLink)} show a link if course run ${isIf(
      isLinkable
    )} linkable`, async () => {
      isLinkableStub.returns(isLinkable)
      const exampleCoursewareUrl = "http://example.com/my-course"
      userEnrollments[0].run.courseware_url = exampleCoursewareUrl
      const enrollment = { ...userEnrollments[0] }

      helper.mockGetRequest("/api/enrollments/", [enrollment])
      const { wrapper } = await renderPage()
      const enrolledItems = wrapper.find(".enrolled-item")
      assert.lengthOf(enrolledItems, 1)
      assert.equal(enrolledItems.at(0).find("a").exists(), expCourseLink)

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
    helper.mockGetRequest("/api/enrollments/", userEnrollments)
    const { wrapper } = await renderPage()
    const enrolledItems = wrapper.find(".enrolled-item")
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
  ;[
    [true, 204],
    [false, 400]
  ].forEach(([success, returnedStatusCode]) => {
    it(`allows users to unenroll and handles ${returnedStatusCode} response`, async () => {
      // @ts-ignore
      window.scrollTo = sinon.stub()
      const enrollmentIndex = 0
      const enrollment = userEnrollments[enrollmentIndex]
      const expectedUserMsgProps = success
        ? {
          type: ALERT_TYPE_SUCCESS,
          msg:  `You have been successfully unenrolled from ${enrollment.run.title}.`
        }
        : {
          type: ALERT_TYPE_DANGER,
          msg:  `Something went wrong with your request to unenroll. Please contact support at ${SETTINGS.support_email}.`
        }
      isWithinEnrollmentPeriodStub.returns(true)
      const mockDelete = helper.mockDeleteRequest(
        `/api/enrollments/${enrollment.id}/`,
        null,
        returnedStatusCode as number
      )

      const { wrapper } = await renderPage()
      const enrolledItem = wrapper.find(".enrolled-item").at(enrollmentIndex)
      const unenrollBtn = enrolledItem.find("Dropdown DropdownItem").at(0)
      assert.isTrue(unenrollBtn.exists())
      await act(async () => {
        // @ts-ignore
        await unenrollBtn.prop("onClick")()
      })
      sinon.assert.called(mockDelete)
      sinon.assert.calledWith(isWithinEnrollmentPeriodStub, enrollment.run)
      sinon.assert.calledOnceWithExactly(
        addNotificationStub,
        "unenroll-status",
        {
          type:  expectedUserMsgProps.type,
          props: {
            text: expectedUserMsgProps.msg
          }
        }
      )
    })
  })
  ;([
    [true, "enables the unenroll button and renders no tooltip"],
    [false, "disables the unenroll button and renders tooltip"]
  ] as [boolean, string][]).forEach(([isEnrollable, desc]) => {
    it(`${desc} if the enrollment period ${isIf(
      isEnrollable
    )} active`, async () => {
      isWithinEnrollmentPeriodStub.returns(isEnrollable)
      const enrollmentIndex = 0
      const enrollment = userEnrollments[enrollmentIndex]
      const { wrapper } = await renderPage()
      const enrolledItem = wrapper.find(".enrolled-item").at(enrollmentIndex)
      const unenrollBtn = enrolledItem
        .find("Dropdown DropdownItem")
        .at(enrollmentIndex)
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
  ;[
    [true, 200],
    [false, 400]
  ].forEach(([success, returnedStatusCode]) => {
    it(`allow users to subscribe to course emails and handles ${returnedStatusCode} response`, async () => {
      // @ts-ignore
      window.scrollTo = sinon.stub()
      const enrollmentIndex = 0
      const enrollment = userEnrollments[enrollmentIndex]
      enrollment.edx_emails_subscription = false

      helper.mockPatchRequest(
        `/api/enrollments/${enrollment.id}/`,
        {},
        returnedStatusCode as number
      )

      const { wrapper } = await renderPage()
      const enrolledItems = wrapper.find(".enrolled-item").at(enrollmentIndex)
      const unsubscribeBtn = enrolledItems.find("Dropdown DropdownItem").at(1)
      assert.isTrue(unsubscribeBtn.exists())
      await act(async () => {
        // @ts-ignore
        await unsubscribeBtn.prop("onClick")()
      })
      sinon.assert.calledTwice(helper.handleRequestStub)
      sinon.assert.calledOnceWithExactly(
        addNotificationStub,
        "subscription-status",
        {
          type:  success ? ALERT_TYPE_SUCCESS : ALERT_TYPE_DANGER,
          props: {
            text: success
              ? `You have been successfully subscribed to course ${enrollment.run.title} emails.`
              : `Something went wrong with your request to course emails subscription. Please contact support at ${SETTINGS.support_email}.`
          }
        }
      )
    })
  })
})
