// @flow
import React from "react"
import moment from "moment"

import { assert } from "chai"
import { shallow } from "enzyme"

import { EnrolledItemCard } from "./EnrolledItemCard"
import { shouldIf } from "../lib/test_utils"
import IntegrationTestHelper from "../util/integration_test_helper"
import {
  makeCourseRunEnrollment,
  makeCourseRunEnrollmentWithProduct,
  makeProgramEnrollment,
  makeLearnerRecordGrade
} from "../factories/course"
import { makeUser } from "../factories/user"

describe("EnrolledItemCard", () => {
  let helper,
    renderedCard,
    userEnrollment,
    currentUser,
    enrollmentCardProps,
    toggleProgramDrawer,
    redirectToCourseHomepage

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    userEnrollment = makeCourseRunEnrollment()
    currentUser = makeUser()
    enrollmentCardProps = {
      enrollment:           userEnrollment,
      currentUser:          currentUser,
      deactivateEnrollment: helper.sandbox
        .stub()
        .withArgs(userEnrollment.id)
        .returns(Promise),
      deactivateProgramEnrollment: helper.sandbox
        .stub()
        .withArgs(userEnrollment.id)
        .returns(Promise),
      courseEmailsSubscription: helper.sandbox
        .stub()
        .withArgs(userEnrollment.id, "test")
        .returns(Promise),
      addUserNotification: helper.sandbox.stub().returns(Function)
    }
    toggleProgramDrawer = helper.sandbox.stub().returns(Function)
    redirectToCourseHomepage = helper.sandbox.stub().returns(Function)

    renderedCard = () =>
      shallow(
        <EnrolledItemCard
          key={enrollmentCardProps.enrollment.id}
          enrollment={enrollmentCardProps.enrollment}
          currentUser={currentUser}
          deactivateEnrollment={enrollmentCardProps.deactivateEnrollment}
          deactivateProgramEnrollment={
            enrollmentCardProps.deactivateProgramEnrollment
          }
          courseEmailsSubscription={
            enrollmentCardProps.courseEmailsSubscription
          }
          addUserNotification={enrollmentCardProps.addUserNotification}
          toggleProgramDrawer={toggleProgramDrawer}
          isLoading={false}
          isProgramCard={false}
          redirectToCourseHomepage={redirectToCourseHomepage}
        />
      )
  })

  afterEach(() => {
    helper.cleanup()
  })
  ;["audit", "verified", "program"].forEach(mode => {
    it(`renders the card for enrollment mode ${mode}`, async () => {
      const testEnrollment =
        mode === "program" ?
          makeProgramEnrollment() :
          makeCourseRunEnrollmentWithProduct()
      userEnrollment = testEnrollment
      enrollmentCardProps.enrollment = testEnrollment
      const inner = await renderedCard()
      const enrolledItems = inner.find(".enrolled-item")
      assert.lengthOf(enrolledItems, 1)
      const enrolledItem = enrolledItems.at(0)
      if (mode !== "program") {
        assert.equal(
          enrolledItem.find("h2").text(),
          userEnrollment.run.course.title
        )
        if (mode === "verified") {
          const pricingLinks = inner.find(".pricing-links")
          assert.isFalse(pricingLinks.exists())
        }
      } else {
        assert.equal(
          enrolledItem.find("h2").text(),
          testEnrollment.program.title
        )
      }
    })
  })
  ;["audit", "verified"].forEach(mode => {
    it(`renders the card in mode ${mode} without upsell message when ecommerce disabled`, async () => {
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
        const pricingLinks = inner.find(".pricing-links")
        assert.isFalse(pricingLinks.exists())
      }
    })
  })
  ;["audit", "verified"].forEach(mode => {
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

  it("doesn't renders the course passed label if course is passed but no certificate", async () => {
    // If there are no grades at all
    let inner = await renderedCard()
    let coursePassed = inner
      .find(".enrolled-item")
      .find(".badge-enrolled-passed")
    assert.isFalse(coursePassed.exists())

    // If the user has passed grades but no certificate
    const grade = makeLearnerRecordGrade()
    grade.passed = true
    enrollmentCardProps.enrollment.grades = [grade]
    inner = await renderedCard()
    coursePassed = inner.find(".enrolled-item").find(".badge-enrolled-passed")
    assert.isFalse(coursePassed.exists())
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

  it("Course detail shows `Starts` when start date and end date are in the future", async () => {
    enrollmentCardProps.enrollment.run.start_date = moment().add(7, "d")
    enrollmentCardProps.enrollment.run.end_date = moment().add(14, "d")
    const inner = await renderedCard()
    const detail = inner.find(".enrolled-item").find(".detail")
    assert.isTrue(detail.exists())
    const detailText = detail.find("span").at(0).text()
    assert.isTrue(detailText.startsWith(" | Starts"))
  })

  it("Course detail shows `Starts` when start date is in the future and end date is null", async () => {
    enrollmentCardProps.enrollment.run.start_date = moment().add(7, "d")
    enrollmentCardProps.enrollment.run.end_date = null
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

  it("Course detail does not display course details (about page) link if course page is not published", async () => {
    enrollmentCardProps.enrollment.run.course.page.live = false
    const inner = await renderedCard()
    const enrollmentExtraLinks = inner
      .find(".enrolled-item")
      .find(".enrollment-extra-links")
    assert.isTrue(enrollmentExtraLinks.exists())
    const courseDetailsPageLink = enrollmentExtraLinks.find("a").at(0)
    assert.isFalse(courseDetailsPageLink.exists())
  })

  it("Course detail does display course details (about page) link if course page is published", async () => {
    enrollmentCardProps.enrollment.run.course.page.live = true
    const inner = await renderedCard()
    const enrollmentExtraLinks = inner
      .find(".enrolled-item")
      .find(".enrollment-extra-links")
    assert.isTrue(enrollmentExtraLinks.exists())
    const courseDetailsPageLink = enrollmentExtraLinks.find("a").at(0)
    assert.isTrue(courseDetailsPageLink.exists())
  })

  it("renders the unenrollment verification modal", async () => {
    const inner = await renderedCard()
    const modalId = `run-unenrollment-${userEnrollment.id}-modal`
    const modals = inner.find(`#${modalId}`)
    if (userEnrollment.enrollment_mode === "verified") {
      assert.lengthOf(modals, 1)
    }
  })
  ;[
    [true, "verified"],
    [true, "audit"]
  ].forEach(([activationStatus, enrollmentType]) => {
    it(`${shouldIf(
      activationStatus
    )} activate the unenrollment verification modal if the enrollment type is ${enrollmentType}`, async () => {
      enrollmentCardProps.enrollment.enrollment_mode = enrollmentType
      const inner = await renderedCard()
      const unenrollButton = inner.find(".unenroll-btn").at(0)

      assert.isTrue(unenrollButton.exists())
      await unenrollButton.prop("onClick")()

      const verifiedUnenrollmodal = inner.find("Modal").at(0)
      assert.isTrue(verifiedUnenrollmodal.exists())
    })
  })
  it("renders the program unenrollment verification modal", async () => {
    enrollmentCardProps.enrollment = makeProgramEnrollment()

    const inner = await renderedCard()
    const modalId = `program-unenrollment-${enrollmentCardProps.enrollment.program.id}-modal`
    const modals = inner.find(`#${modalId}`)
    assert.lengthOf(modals, 1)
  })
  ;["audit", "verified", "program"].forEach(mode => {
    it(`renders the card for enrollment mode ${mode}`, async () => {
      const testEnrollment =
        mode === "program" ?
          makeProgramEnrollment() :
          makeCourseRunEnrollmentWithProduct()
      userEnrollment = testEnrollment
      enrollmentCardProps.enrollment = testEnrollment
      const inner = await renderedCard()
      const enrolledItems = inner.find(".enrolled-item")
      assert.lengthOf(enrolledItems, 1)
      const enrolledItem = enrolledItems.at(0)
      if (mode !== "program") {
        assert.equal(
          enrolledItem.find("h2").text(),
          userEnrollment.run.course.title
        )
        if (mode === "verified") {
          const pricingLinks = inner.find(".pricing-links")
          assert.isFalse(pricingLinks.exists())
        }
      } else {
        assert.equal(
          enrolledItem.find("h2").text(),
          testEnrollment.program.title
        )
      }
    })
  })
  it("Test", async () => {
    const testEnrollment = makeCourseRunEnrollmentWithProduct()
    userEnrollment = testEnrollment
    enrollmentCardProps.enrollment = testEnrollment
    enrollmentCardProps.enrollment.enrollment_mode = "audit"
    const inner = await renderedCard()
    const enrollmentExtraLinks = inner
      .find(".enrolled-item")
      .find(".certificate-upgrade-message")
    assert.isTrue(enrollmentExtraLinks.exists())
    const courseDetailsPageLink = enrollmentExtraLinks.find("b").at(0)
    assert.isTrue(courseDetailsPageLink.exists())
  })
})
