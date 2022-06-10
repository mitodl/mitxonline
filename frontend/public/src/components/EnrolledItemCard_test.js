/* global SETTINGS: false */
// @flow
import React from "react"

import { assert } from "chai"
import moment from "moment"
import sinon from "sinon"
import { Formik } from "formik"
import { shallow } from "enzyme"

import EnrolledItemCard, {
  EnrolledItemCard as InnerEnrolledItemCard
} from "./EnrolledItemCard"
import { ALERT_TYPE_DANGER, ALERT_TYPE_SUCCESS } from "../constants"
import { formatPrettyDateTimeAmPmTz } from "../lib/util"
import { shouldIf, isIf } from "../lib/test_utils"
import IntegrationTestHelper from "../util/integration_test_helper"
import { makeCourseRunEnrollment } from "../factories/course"
import { makeUser } from "../factories/user"
import * as courseApi from "../lib/courseApi"

describe("EnrolledItemCard", () => {
  let helper,
    renderedCard,
    userEnrollment,
    currentUser,
    isLinkableStub,
    enrollmentCardProps

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollment = makeCourseRunEnrollment()
    currentUser = makeUser()
    isLinkableStub = helper.sandbox.stub(courseApi, "isLinkableCourseRun")
    enrollmentCardProps = {
      enrollment:           userEnrollment,
      currentUser:          currentUser,
      deactivateEnrollment: helper.sandbox
        .stub()
        .withArgs(userEnrollment.id)
        .returns(Promise),
      courseEmailsSubscription: helper.sandbox
        .stub()
        .withArgs(userEnrollment.id, "test")
        .returns(Promise),
      addUserNotification: helper.sandbox.stub().returns(Function)
    }

    renderedCard = () =>
      shallow(
        <EnrolledItemCard
          key={enrollmentCardProps.enrollment.id}
          enrollment={enrollmentCardProps.enrollment}
          currentUser={currentUser}
          deactivateEnrollment={enrollmentCardProps.deactivateEnrollment}
          courseEmailsSubscription={
            enrollmentCardProps.courseEmailsSubscription
          }
          addUserNotification={enrollmentCardProps.addUserNotification}
        />
      )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders the card", async () => {
    const inner = await renderedCard()
    const enrolledItems = inner.find(".enrolled-item")
    assert.lengthOf(enrolledItems, 1)
    const enrolledItem = enrolledItems.at(0)
    assert.equal(
      enrolledItem.find("h2").text(),
      userEnrollment.run.course.title
    )
  })

  it("renders the unenrollment verification modal", async () => {
    const inner = await renderedCard()
    const modalId = `verified-unenrollment-${userEnrollment.id}-modal`
    const modals = inner.find(`#${modalId}`)
    assert.lengthOf(modals, 1)
  })
  ;[
    [true, "verified"],
    [false, "audit"]
  ].forEach(([activationStatus, enrollmentType]) => {
    it(`${shouldIf(
      activationStatus
    )} activate the unenrollment verification modal if the enrollment type is ${enrollmentType}`, async () => {
      enrollmentCardProps.enrollment.enrollment_mode = enrollmentType
      const inner = await renderedCard()
      const unenrollButton = inner.find("Dropdown DropdownItem").at(0)

      assert.isTrue(unenrollButton.exists())
      await unenrollButton.prop("onClick")()

      const modal = inner.find("Modal").at(0)
      assert.isTrue(modal.exists())
      assert.isTrue(modal.prop("isOpen") === activationStatus)
    })
  })
})
