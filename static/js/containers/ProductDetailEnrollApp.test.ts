import { assert } from "chai"
import { makeCourseRunDetail } from "../factories/course"
import * as courseApi from "../lib/courseApi"
import { courseRunsSelector } from "../lib/queries/courseRuns"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import ProductDetailEnrollApp from "./ProductDetailEnrollApp"

describe("ProductDetailEnrollApp", () => {
  const courseRun = makeCourseRunDetail()
  const courseId = courseRun.course.readable_id

  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    isWithinEnrollmentPeriodStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    helper.mockGetRequest(
      `/api/course_runs/?relevant_to=${encodeURIComponent(courseId)}`,
      [courseRun]
    )
    renderPage = helper.configureRenderer(ProductDetailEnrollApp, {
      courseId
    })
    isWithinEnrollmentPeriodStub = helper.sandbox.stub(
      courseApi,
      "isWithinEnrollmentPeriod"
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("checks for enroll now button", async () => {
    isWithinEnrollmentPeriodStub.returns(true)
    const { wrapper } = await renderPage()
    assert.equal(wrapper.find("button").at(0).text(), "Enroll now")
  })

  it("checks for enroll now button should not appear if enrollment start in future", async () => {
    isWithinEnrollmentPeriodStub.returns(false)
    const { wrapper } = await renderPage()
    assert.isNotOk(wrapper.find("button").at(0).exists())
  })

  it("checks for enroll now button should appear if enrollment start not in future", async () => {
    isWithinEnrollmentPeriodStub.returns(true)
    const { wrapper } = await renderPage()
    assert.equal(wrapper.find("button").at(0).text(), "Enroll now")
  })

  it("checks for enrolled button", async () => {
    const userEnrollment = makeCourseRunDetail()
    const expectedResponse = { ...userEnrollment, is_enrolled: true }
    helper.mockGetRequest(
      `/api/course_runs/?relevant_to=${encodeURIComponent(courseId)}`,
      [expectedResponse]
    )
    const { wrapper, store } = await renderPage()
    assert.equal(wrapper.find("a").at(0).text(), "Enrolled ✓")
    // @ts-ignore
    assert.equal(courseRunsSelector(store.getState())[0], expectedResponse)
  })
})
