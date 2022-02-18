/* global SETTINGS: false */
// @flow
import { assert } from "chai"

import IntegrationTestHelper from "../util/integration_test_helper"
import ProductDetailEnrollApp, {
  ProductDetailEnrollApp as InnerProductDetailEnrollApp
} from "./ProductDetailEnrollApp"

import { courseRunsSelector } from "../lib/queries/courseRuns"
import {
  makeCourseRunDetail,
  makeCourseRunEnrollment
} from "../factories/course"

import * as courseApi from "../lib/courseApi"

import sinon from "sinon"
import { makeUser } from "../factories/user"

describe("ProductDetailEnrollApp", () => {
  let helper, renderPage, isWithinEnrollmentPeriodStub, courseRun, currentUser

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    courseRun = makeCourseRunDetail()
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
    SETTINGS.features = { upgrade_dialog: false, enable_discount_ui: false }

    isWithinEnrollmentPeriodStub = helper.sandbox.stub(
      courseApi,
      "isWithinEnrollmentPeriod"
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

  it("checks for enrolled button", async () => {
    const userEnrollment = makeCourseRunEnrollment()
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

    assert.equal(
      inner
        .find("a")
        .at(0)
        .text(),
      "Enrolled ✓"
    )
    assert.equal(courseRunsSelector(store.getState())[0], expectedResponse)
  })
  ;[[true, 201], [false, 400]].forEach(([success, returnedStatusCode]) => {
    it(`shows dialog to upgrade user enrollment and handles ${returnedStatusCode} response`, async () => {
      isWithinEnrollmentPeriodStub.returns(true)
      SETTINGS.features.upgrade_dialog = true
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
    })
  })
})
