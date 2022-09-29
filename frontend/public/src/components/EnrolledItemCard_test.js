// @flow
/* global SETTINGS:false */
import React from "react"
import moment from "moment"

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
    enrollmentCardProps,
    isFinancialAssistanceAvailableStub,
    closeDrawer


  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollment = makeCourseRunEnrollment()
    currentUser = makeUser()
    SETTINGS.features = { upgrade_dialog: true, disable_discount_ui: false, enable_program_ui: false }
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
          closeDrawer={closeDrawer}
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
    it("renders the card without upsell message when ecommerce disabled", async () => {
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
      } else {
        SETTINGS.features = { upgrade_dialog: false, disable_discount_ui: false, enable_program_ui: false }
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

  it("Course detail shows `Active` when start date in past", async () => {
    enrollmentCardProps.enrollment.run.start_date = moment("2021-02-08")
    enrollmentCardProps.enrollment.run.end_date = moment().add(7, "d")
    const inner = await renderedCard()
    const detail = inner.find(".enrolled-item").find(".detail")
    assert.isTrue(detail.exists())
    const detailText = detail.find("span").find("span").at(0).text()
    assert.isTrue(detailText.startsWith(" | Active"))
  })

  it("Course detail shows `Starts` when start date in future", async () => {
    enrollmentCardProps.enrollment.run.start_date = moment().add(7, "d")
    const inner = await renderedCard()
    const detail = inner.find(".enrolled-item").find(".detail")
    assert.isTrue(detail.exists())
    const detailText = detail.find("span").at(0).text()
    assert.isTrue(detailText.startsWith(" | Starts"))
  })

  it("Course detail shows `Ended` when end date in past", async () => {
    enrollmentCardProps.enrollment.run.end_date = moment().add(-7, "d")
    const inner = await renderedCard()
    const detail = inner.find(".enrolled-item").find(".detail")
    assert.isTrue(detail.exists())
    const detailText = detail.find("span").at(0).text()
    assert.isTrue(detailText.startsWith(" | Ended"))
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
      const extraLinks = inner.find(".enrollment-extra-links").at(1)
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
