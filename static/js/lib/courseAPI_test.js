import { isLinkableCourseRun } from "./courseApi"
import { assert } from "chai"
import moment from "moment"

import { makeCourseRunEnrollment } from "../factories/course"

describe("Course API", () => {
  let userEnrollment
  beforeEach(() => {
    userEnrollment = makeCourseRunEnrollment()
  })

  describe("isLinkableCourseRun", () => {
    it("returns false when courseware_url is nil", () => {
      const past = moment().add(-10, "days"),
        future = moment().add(10, "days")
      const exampleCoursewareUrl = null
      userEnrollment.run.courseware_url = exampleCoursewareUrl
      userEnrollment.run.start_date = past.toISOString()
      userEnrollment.run.end_date = future.toISOString()
      assert.isFalse(isLinkableCourseRun(userEnrollment.run))
    })

    it("returns false when start date is nil", () => {
      const future = moment().add(10, "days")
      const exampleCoursewareUrl = "http://example.com/my-course"
      userEnrollment.run.courseware_url = exampleCoursewareUrl
      userEnrollment.run.start_date = null
      userEnrollment.run.end_date = future.toISOString()
      assert.isFalse(isLinkableCourseRun(userEnrollment.run))
    })

    it("returns false when start date is in future", () => {
      const future = moment().add(10, "days")
      const exampleCoursewareUrl = "http://example.com/my-course"
      userEnrollment.run.courseware_url = exampleCoursewareUrl
      userEnrollment.run.start_date = future.toISOString()
      userEnrollment.run.end_date = null
      assert.isFalse(isLinkableCourseRun(userEnrollment.run))
    })

    it("returns false when end date is in past", () => {
      const farPast = moment().add(-10, "days")
      const nearPast = moment().add(-1, "days")
      const exampleCoursewareUrl = "http://example.com/my-course"
      userEnrollment.run.courseware_url = exampleCoursewareUrl
      userEnrollment.run.start_date = farPast.toISOString()
      userEnrollment.run.end_date = nearPast.toISOString()
      assert.isFalse(isLinkableCourseRun(userEnrollment.run))
    })

    it("returns true if course run start date is in the past and end date is in the future", () => {
      const past = moment().add(-10, "days"),
        future = moment().add(10, "days")
      const exampleCoursewareUrl = "http://example.com/my-course"
      userEnrollment.run.courseware_url = exampleCoursewareUrl
      userEnrollment.run.start_date = past.toISOString()
      userEnrollment.run.end_date = future.toISOString()
      assert.isTrue(isLinkableCourseRun(userEnrollment.run))
    })
  })
})
