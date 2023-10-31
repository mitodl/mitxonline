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

import sinon from "sinon"
import { makeUser } from "../factories/user"

describe("CourseProductDetailEnroll", () => {
  let helper,
    renderPage,
    isWithinEnrollmentPeriodStub,
    isFinancialAssistanceAvailableStub,
    courseRun,
    course,
    currentUser

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    courseRun = makeCourseRunDetailWithProduct()
    course = makeCourseDetailWithRuns()
    currentUser = makeUser()
    renderPage = helper.configureHOCRenderer(
      CourseProductDetailEnroll,
      InnerCourseProductDetailEnroll,
      {
        entities: {
          courseRuns:  [courseRun],
          courses:     [course],
          currentUser: currentUser
        }
      },
      {}
    )
    SETTINGS.features = {
      "mitxonline-new-product-page": true
    }

    isWithinEnrollmentPeriodStub = helper.sandbox.stub(
      courseApi,
      "isWithinEnrollmentPeriod"
    )
    isFinancialAssistanceAvailableStub = helper.sandbox.stub(
      courseApi,
      "isFinancialAssistanceAvailable"
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders a Loader component", async () => {
    const { inner } = await renderPage({
      queries: {
        courseRuns: {
          isPending: true
        }
      }
    })

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

  it(`shows form based enrollment button when upgrade deadline has passed but course is within enrollment period`, async () => {
    isWithinEnrollmentPeriodStub.returns(true)
    courseRun.is_upgradable = false
    const { inner } = await renderPage()

    sinon.assert.calledWith(
      helper.handleRequestStub,
      "/api/course_runs/?relevant_to=",
      "GET"
    )
    sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")

    const enrollBtn = inner.find("form > button.enroll-now")
    assert.isTrue(enrollBtn.exists())
  })
})
