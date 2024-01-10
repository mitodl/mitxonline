/* global SETTINGS: false */
// @flow
import { assert } from "chai"
import moment from "moment-timezone"
import React from "react"

import IntegrationTestHelper from "../util/integration_test_helper"
import CourseProductDetailEnroll, {
  CourseProductDetailEnroll as InnerCourseProductDetailEnroll
} from "./CourseProductDetailEnroll"

import { courseRunsSelector } from "../lib/queries/courseRuns"
import {
  makeCourseDetailWithRuns,
  makeCourseRunDetail,
  makeCourseRunEnrollment,
  makeCourseRunDetailWithProduct
} from "../factories/course"

import {
  DISCOUNT_TYPE_DOLLARS_OFF,
  DISCOUNT_TYPE_PERCENT_OFF,
  DISCOUNT_TYPE_FIXED_PRICE
} from "../constants"

import * as courseApi from "../lib/courseApi"
import * as reduxqueryreact from "redux-query-react"

import sinon from "sinon"
import { makeUser, makeAnonymousUser } from "../factories/user"

describe("CourseProductDetailEnrollShallowRender", () => {
  let helper,
    renderPage,
    isWithinEnrollmentPeriodStub,
    isFinancialAssistanceAvailableStub,
    courseRun,
    course,
    enrollment,
    currentUser

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    courseRun = makeCourseRunDetailWithProduct()
    course = makeCourseDetailWithRuns()
    enrollment = makeCourseRunEnrollment()
    currentUser = makeUser()

    renderPage = helper.configureShallowRenderer(
      CourseProductDetailEnroll,
      InnerCourseProductDetailEnroll,
      {
        entities: {
          courseRuns:  [courseRun],
          courses:     [course],
          enrollments: [enrollment],
          currentUser: currentUser
        }
      },
      {}
    )

    SETTINGS.features = {
      "mitxonline-new-product-page": true
    }

    isFinancialAssistanceAvailableStub = helper.sandbox.stub(
      courseApi,
      "isFinancialAssistanceAvailable"
    )

    isWithinEnrollmentPeriodStub = helper.sandbox.stub(
      courseApi,
      "isWithinEnrollmentPeriod"
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders a Loader component", async () => {
    const { inner } = await renderPage(
      {
        queries: {
          courseRuns: {
            isPending: true
          }
        }
      },
      { isLoading: true }
    )
    const loader = inner.find("Loader").first()
    assert.isOk(loader.exists())
    assert.isTrue(loader.props().isLoading)
  })

  it("checks for enroll now button", async () => {
    const courseRun = makeCourseRunDetail()
    isWithinEnrollmentPeriodStub.returns(true)
    const { inner } = await renderPage(
      {
        entities: {
          courseRuns: [courseRun]
        },
        queries: {
          courseRuns: {
            isPending: false,
            status:    200
          }
        }
      },
      {}
    )

    assert.equal(
      inner
        .find(".enroll-now")
        .at(0)
        .text(),
      "Enroll now"
    )
  })

  it("checks for enroll now button should not appear if enrollment start in future", async () => {
    const courseRun = makeCourseRunDetail()
    isWithinEnrollmentPeriodStub.returns(false)
    const { inner } = await renderPage(
      {
        entities: {
          courseRuns: [courseRun]
        },
        queries: {
          courseRuns: {
            isPending: false,
            status:    200
          }
        }
      },
      {}
    )

    assert.isNotOk(
      inner
        .find(".enroll-now")
        .at(0)
        .exists()
    )
  })

  it("checks for enroll now button should appear if enrollment start not in future", async () => {
    const courseRun = makeCourseRunDetail()
    isWithinEnrollmentPeriodStub.returns(true)
    const { inner } = await renderPage(
      {
        entities: {
          courseRuns: [courseRun]
        },
        queries: {
          courseRuns: {
            isPending: false,
            status:    200
          }
        }
      },
      {}
    )

    assert.equal(
      inner
        .find(".enroll-now")
        .at(0)
        .text(),
      "Enroll now"
    )
  })

  it("checks for form-based enrollment form if there is no product", async () => {
    const courseRun = makeCourseRunDetail()
    isWithinEnrollmentPeriodStub.returns(true)
    const { inner } = await renderPage(
      {
        entities: {
          courseRuns: [courseRun]
        },
        queries: {
          courseRuns: {
            isPending: false,
            status:    200
          }
        }
      },
      {}
    )

    assert.equal(
      inner
        .find("form > button.enroll-now")
        .at(0)
        .text(),
      "Enroll now"
    )
  })

  it("checks for disabled enrolled button", async () => {
    const userEnrollment = makeCourseRunEnrollment()

    userEnrollment.run["start_date"] = moment().add(2, "M")
    const expectedResponse = {
      ...userEnrollment.run,
      is_enrolled: true
    }

    const { inner, store } = await renderPage(
      {
        entities: {
          courseRuns: [expectedResponse]
        },
        queries: {
          courseRuns: {
            isPending: false,
            status:    200
          }
        }
      },
      {}
    )

    const item = inner.find("a").first()
    assert.isTrue(item.hasClass("disabled"))
    assert.isTrue(
      inner.containsMatchingElement(
        <p>Enrolled and waiting for the course to begin.</p>
      )
    )

    assert.equal(item.text(), "Enrolled ✓")
    assert.equal(courseRunsSelector(store.getState())[0], expectedResponse)
  })

  it("checks for enrolled button", async () => {
    const userEnrollment = makeCourseRunEnrollment()
    userEnrollment.run["start_date"] = moment().add(-2, "M")
    const expectedResponse = {
      ...userEnrollment.run,
      is_enrolled: true
    }

    const { inner, store } = await renderPage(
      {
        entities: {
          courseRuns: [expectedResponse]
        },
        queries: {
          courseRuns: {
            isPending: false,
            status:    200
          }
        }
      },
      {}
    )

    const item = inner.find("a").first()

    assert.isFalse(item.hasClass("disabled"))
    assert.isFalse(
      inner.containsMatchingElement(
        <p>Enrolled and waiting for the course to begin.</p>
      )
    )

    assert.equal(item.text(), "Enrolled ✓")
    assert.equal(courseRunsSelector(store.getState())[0], expectedResponse)
  })
  ;[
    [true, false],
    [false, false],
    [true, true],
    [true, true]
  ].forEach(([userExists, hasMoreDates]) => {
    it(`renders the CourseInfoBox if the user ${
      userExists ? "is logged in" : "is anonymous"
    }`, async () => {
      const entities = {
        currentUser: userExists ? currentUser : makeAnonymousUser(),
        enrollments: []
      }

      const { inner } = await renderPage({
        entities: entities
      })

      assert.isTrue(inner.exists())
      const infobox = inner.find("CourseInfoBox").dive()
      assert.isTrue(infobox.exists())
    })

    it(`CourseInfoBox ${
      hasMoreDates ? "renders" : "does not render"
    } the date selector when the user ${
      userExists ? "is logged in" : "is anonymous"
    } and there is ${
      hasMoreDates ? ">1 courserun" : "one courserun"
    }`, async () => {
      const courseRuns = [courseRun]

      if (hasMoreDates) {
        courseRuns.push(makeCourseRunDetail())
      }

      const entities = {
        currentUser: userExists ? currentUser : makeAnonymousUser(),
        enrollments: [],
        courseRuns:  courseRuns
      }

      const { inner } = await renderPage({
        entities: entities
      })

      assert.isTrue(inner.exists())
      const infobox = inner.find("CourseInfoBox").dive()
      assert.isTrue(infobox.exists())

      const moreDatesLink = infobox.find("button.more-enrollment-info").first()

      if (!hasMoreDates) {
        assert.isFalse(moreDatesLink.exists())
      } else {
        assert.isTrue(moreDatesLink.exists())
        await moreDatesLink.prop("onClick")()

        const selectorBar = infobox.find(".more-dates-enrollment-list")
        assert.isTrue(selectorBar.exists())
      }
    })
  })

  it("CourseInfoBox renders a date selector with Enrolled text if the user is enrolled in one", async () => {
    const secondCourseRun = makeCourseRunDetail()
    const enrollment = {
      ...makeCourseRunEnrollment(),
      run: secondCourseRun
    }

    const entities = {
      currentUser: currentUser,
      enrollments: [enrollment],
      courseRuns:  [courseRun, secondCourseRun]
    }

    const { inner } = await renderPage({
      entities: entities
    })

    assert.isTrue(inner.exists())
    const infobox = inner.find("CourseInfoBox").dive()
    assert.isTrue(infobox.exists())

    const moreDatesLink = infobox.find("button.more-enrollment-info").first()
    await moreDatesLink.prop("onClick")()

    const selectorBar = infobox.find(".more-dates-enrollment-list")
    assert.isTrue(selectorBar.exists())

    const enrolledItem = infobox.find(".more-dates-link.enrolled")
    assert.isTrue(enrolledItem.exists())
  })
  ;[[true], [false]].forEach(([flexPriceApproved]) => {
    it(`shows the flexible pricing available link if the user does not have approved flexible pricing for the course run`, async () => {
      courseRun["approved_flexible_price_exists"] = flexPriceApproved
      courseRun["course"] = {
        page: {
          financial_assistance_form_url: "google.com"
        }
      }
      isWithinEnrollmentPeriodStub.returns(true)
      isFinancialAssistanceAvailableStub.returns(true)
      const { inner } = await renderPage()

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      await enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")

      const flexiblePricingLink = modal.find(".financial-assistance-link").at(0)
      if (flexPriceApproved) {
        assert.isFalse(flexiblePricingLink.exists())
      } else {
        assert.isTrue(flexiblePricingLink.exists())
      }
    })
  })

  it("CourseInfoBox renders the archived message if the course is archived", async () => {
    const courseRun = {
      ...makeCourseRunDetail(),
      is_self_paced:    true,
      enrollment_end:   null,
      enrollment_start: moment()
        .subtract(1, "years")
        .toISOString(),
      start_date: moment()
        .subtract(10, "months")
        .toISOString(),
      end_date: moment()
        .subtract(7, "months")
        .toISOString(),
      upgrade_deadline: null
    }
    const course = {
      ...makeCourseDetailWithRuns(),
      courseruns: [courseRun]
    }

    const entities = {
      currentUser: currentUser,
      enrollments: [],
      courseRuns:  [courseRun],
      courses:     [course]
    }

    const { inner } = await renderPage({
      entities: entities
    })

    assert.isTrue(inner.exists())
    const infobox = inner.find("CourseInfoBox").dive()
    assert.isTrue(infobox.exists())

    const archivedMessage = infobox.find("div.course-archived-message")
    assert.isTrue(archivedMessage.exists())

    const contentAvailabilityMessage = infobox.find(
      "div.course-timing-message div.enrollment-info-text"
    )
    assert.isTrue(contentAvailabilityMessage.exists())
    assert.isTrue(
      contentAvailabilityMessage
        .first()
        .text()
        .includes("Course content available anytime")
    )
  })

  it(`shows form based enrollment button when upgrade deadline has passed but course is within enrollment period`, async () => {
    isWithinEnrollmentPeriodStub.returns(true)
    courseRun.is_upgradable = false
    course.next_run_id = courseRun.id

    const { inner } = await renderPage(
      {
        entities: {
          courseRuns: [courseRun],
          courses:    [course]
        },
        queries: {
          courseRuns: {
            isPending: false,
            status:    200
          },
          courses: {
            isPending: false,
            status:    200
          }
        }
      },
      { courseId: course.id }
    )

    const enrollBtn = inner.find("form > button.enroll-now")
    assert.isTrue(enrollBtn.exists())
  })
  ;[
    [true, 201],
    [false, 400]
  ].forEach(([__success, returnedStatusCode]) => {
    it(`shows dialog to upgrade user enrollment with flexible dollars-off discount and handles ${returnedStatusCode} response`, async () => {
      courseRun["products"] = [
        {
          id:                     1,
          price:                  10,
          product_flexible_price: {
            amount:        1,
            discount_type: DISCOUNT_TYPE_DOLLARS_OFF
          }
        }
      ]
      isWithinEnrollmentPeriodStub.returns(true)
      const { inner } = await renderPage()

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")
      const upgradeForm = modal.find("form").at(0)
      assert.isTrue(upgradeForm.exists())

      assert.equal(upgradeForm.find("input[type='hidden']").prop("value"), "1")

      assert.equal(
        inner
          .find("#certificate-price-info")
          .at(0)
          .text(),
        "$9.00"
      )
    })
    it(`shows dialog to upgrade user enrollment with flexible percent-off discount and handles ${returnedStatusCode} response`, async () => {
      courseRun["products"] = [
        {
          id:                     1,
          price:                  10,
          product_flexible_price: {
            amount:        10,
            discount_type: DISCOUNT_TYPE_PERCENT_OFF
          }
        }
      ]
      isWithinEnrollmentPeriodStub.returns(true)
      const { inner } = await renderPage()

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      await enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")
      const upgradeForm = modal.find("form").at(0)
      assert.isTrue(upgradeForm.exists())

      assert.equal(upgradeForm.find("input[type='hidden']").prop("value"), "1")

      assert.equal(
        inner
          .find("#certificate-price-info")
          .at(0)
          .text()
          .at(1),
        "9"
      )
    })
    it(`shows dialog to upgrade user enrollment with flexible fixed-price discount and handles ${returnedStatusCode} response`, async () => {
      courseRun["products"] = [
        {
          id:                     1,
          price:                  10,
          product_flexible_price: {
            amount:        9,
            discount_type: DISCOUNT_TYPE_FIXED_PRICE
          }
        }
      ]
      isWithinEnrollmentPeriodStub.returns(true)
      isFinancialAssistanceAvailableStub.returns(false)
      const { inner } = await renderPage()

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      await enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")
      const upgradeForm = modal.find("form").at(0)
      assert.isTrue(upgradeForm.exists())

      assert.equal(upgradeForm.find("input[type='hidden']").prop("value"), "1")

      assert.equal(
        inner
          .find("#certificate-price-info")
          .at(0)
          .text()
          .at(1),
        "9"
      )
    })
  })

  it(`shows the enroll button and upsell message, and checks for enrollments when the enroll button is clicked`, async () => {
    courseRun["products"] = [
      {
        id:                     1,
        price:                  10,
        product_flexible_price: {}
      }
    ]
    isWithinEnrollmentPeriodStub.returns(true)

    const { inner } = await renderPage()

    const enrollBtn = inner.find(".enroll-now").at(0)
    assert.isTrue(enrollBtn.exists())
    await enrollBtn.prop("onClick")()
  })
  ;[
    ["shows", "one", false],
    ["shows", "multiple", true]
  ].forEach(([showsQualifier, runsQualifier, multiples]) => {
    it(`${showsQualifier} the course run selector for a course with ${runsQualifier} active run${
      multiples ? "s" : ""
    }`, async () => {
      courseRun["products"] = [
        {
          id:                     1,
          price:                  10,
          product_flexible_price: {
            amount:        10,
            discount_type: DISCOUNT_TYPE_PERCENT_OFF
          }
        }
      ]
      const courseRuns = [courseRun]
      if (multiples) {
        courseRuns.push(courseRun)
      }

      isWithinEnrollmentPeriodStub.returns(true)
      const { inner } = await renderPage({
        entities: {
          courseRuns:  courseRuns,
          courses:     [course],
          enrollments: [enrollment],
          currentUser: currentUser
        }
      })

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      await enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")
      const upgradeForm = modal.find("form").at(0)
      assert.isTrue(upgradeForm.exists())

      const selectorControl = modal.find(".date-selector-button-bar").at(0)
      assert.isTrue(selectorControl.exists())

      const selectorControlItems = selectorControl.find("option")
      if (multiples) {
        assert.isTrue(selectorControlItems.length === 2)
      } else {
        assert.isTrue(selectorControlItems.length === 1)
      }
    })
  })
})
