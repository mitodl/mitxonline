/* global SETTINGS: false */
// @flow
import { assert } from "chai"
import moment from "moment-timezone"
import React from "react"

import IntegrationTestHelper from "../util/integration_test_helper"
import ProductDetailEnrollApp, {
  ProductDetailEnrollApp as InnerProductDetailEnrollApp
} from "./ProductDetailEnrollApp"

import { courseRunsSelector } from "../lib/queries/courseRuns"
import {
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

describe("ProductDetailEnrollApp", () => {
  let helper,
    renderPage,
    isWithinEnrollmentPeriodStub,
    isFinancialAssistanceAvailableStub,
    courseRun,
    currentUser

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    courseRun = makeCourseRunDetailWithProduct()
    currentUser = makeUser()
    courseRun["products"] = [{ id: 1 }]
    renderPage = helper.configureHOCRenderer(
      ProductDetailEnrollApp,
      InnerProductDetailEnrollApp,
      {
        entities: {
          courseRuns:  [courseRun],
          currentUser: currentUser
        }
      },
      {}
    )
    SETTINGS.features = { enable_program_ui: false }

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

    assert.isTrue(inner.props().isLoading)
    const loader = inner.find("Loader")
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

      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/course_runs/?relevant_to=",
        "GET"
      )
      sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      await enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")
      const upgradeForm = modal.find("form").at(0)
      assert.isTrue(upgradeForm.exists())

      assert.equal(upgradeForm.find("input[type='hidden']").prop("value"), "1")

      assert.equal(
        inner
          .find(".text-right")
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

      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/course_runs/?relevant_to=",
        "GET"
      )
      sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      await enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")
      const upgradeForm = modal.find("form").at(0)
      assert.isTrue(upgradeForm.exists())

      assert.equal(upgradeForm.find("input[type='hidden']").prop("value"), "1")

      assert.equal(
        inner
          .find(".text-right")
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

      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/course_runs/?relevant_to=",
        "GET"
      )
      sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")

      const enrollBtn = inner.find(".enroll-now").at(0)
      assert.isTrue(enrollBtn.exists())
      await enrollBtn.prop("onClick")()

      const modal = inner.find(".upgrade-enrollment-modal")
      const upgradeForm = modal.find("form").at(0)
      assert.isTrue(upgradeForm.exists())

      assert.equal(upgradeForm.find("input[type='hidden']").prop("value"), "1")

      assert.equal(
        inner
          .find(".text-right")
          .at(0)
          .text()
          .at(1),
        "9"
      )
    })
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
  ;[[true], [false]].forEach(([flexPriceApproved]) => {
    it(`shows the flexible pricing available link if the user does not have approved flexible pricing for the course run`, async () => {
      courseRun["approved_flexible_price_exists"] = flexPriceApproved
      isWithinEnrollmentPeriodStub.returns(true)
      isFinancialAssistanceAvailableStub.returns(true)
      const { inner } = await renderPage()

      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/course_runs/?relevant_to=",
        "GET"
      )
      sinon.assert.calledWith(helper.handleRequestStub, "/api/users/me", "GET")

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
})
