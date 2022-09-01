/* global SETTINGS: false */
// @flow
import React from "react"

import { assert } from "chai"
import { shallow } from "enzyme"

import EnrolledItemCard from "./EnrolledItemCard"
import { shouldIf } from "../lib/test_utils"
import IntegrationTestHelper from "../util/integration_test_helper"
import { makeCourseRunEnrollment, makeCourseRunEnrollmentWithProduct } from "../factories/course"
import { makeUser } from "../factories/user"
import * as courseApi from "../lib/courseApi"

describe("EnrolledItemCard", () => {
  let helper,
    renderedCard,
    userEnrollment,
    currentUser,
    isLinkableStub,
    enrollmentCardProps,
    isFinancialAssistanceAvailableStub


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
      addUserNotification: helper.sandbox.stub().returns(Function),
    },
    isFinancialAssistanceAvailableStub = helper.sandbox.stub(
      courseApi,
      "isFinancialAssistanceAvailable"
    )

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

  ;[
    "audit",
    "verified"
  ].forEach(([mode]) => {
    it("renders the card", async () => {
      const testEnrollment = makeCourseRunEnrollmentWithProduct()
      userEnrollment = testEnrollment
      enrollmentCardProps.enrollment = testEnrollment
      const inner = await renderedCard()
      const enrolledItems = inner.find(".enrolled-item")
      assert.lengthOf(enrolledItems, 1)
      const enrolledItem = enrolledItems.at(0)
      assert.equal(
        enrolledItem.find("h2").text(),
        userEnrollment.run.course.title
      )
      if (mode === "verified") {
        const pricingLinks = inner.find(".pricing-links")
        assert.isFalse(pricingLinks.exists())
      }
    })
  })

  ;[
    "audit",
    "verified"
  ].forEach(([mode]) => {
    it("does not render the pricing links when upgrade deadline has passed", async () => {
      enrollmentCardProps.enrollment.enrollment_mode = mode
      const inner = await renderedCard()
      const enrolledItems = inner.find(".enrolled-item")
      assert.lengthOf(enrolledItems, 1)
      const enrolledItem = enrolledItems.at(0)
      assert.equal(
        enrolledItem.find("h2").text(),
        userEnrollment.run.course.title
      )
      const pricingLinks = inner.find(".pricing-links")
      assert.isFalse(pricingLinks.exists())
    })
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

  ;[
    [true],
    [false]
  ].forEach(([approvedFlexiblePrice]) => {
    it("renders the financial assistance link", async () => {
      isFinancialAssistanceAvailableStub.returns(true)
      userEnrollment = makeCourseRunEnrollmentWithProduct()
      userEnrollment["enrollment_mode"] = "audit"
      userEnrollment["approved_flexible_price_exists"] = approvedFlexiblePrice
      enrollmentCardProps.enrollment = userEnrollment
      const inner = await renderedCard()
      const extraLinks = inner.find(".enrollment-extra-links").at(0)
      if (approvedFlexiblePrice) {
        const text = extraLinks.find("a").at(0)
        assert.isFalse(text.exists())
      } else {
        const text = extraLinks.find("a").at(0).text()
        assert.equal(text, "Financial assistance?")
      }
    })
  })
})
