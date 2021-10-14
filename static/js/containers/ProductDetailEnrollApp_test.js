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

describe("ProductDetailEnrollApp", () => {
  let helper, renderPage

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    renderPage = helper.configureHOCRenderer(
      ProductDetailEnrollApp,
      InnerProductDetailEnrollApp,
      {},
      {}
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
        .find("button")
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
})
