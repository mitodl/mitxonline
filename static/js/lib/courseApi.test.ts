import { assert } from "chai"
import moment from "moment"
import { makeCourseRunDetail } from "../factories/course"
import { makeUser } from "../factories/user"
import { LoggedInUser } from "../types/auth"
import { CourseRunDetail } from "../types/course"
import { isLinkableCourseRun, isWithinEnrollmentPeriod } from "./courseApi"

describe("Course API", () => {
  const past = moment().add(-10, "days").toISOString(),
    farPast = moment().add(-50, "days").toISOString(),
    future = moment().add(10, "days").toISOString(),
    farFuture = moment().add(50, "days").toISOString(),
    exampleUrl = "http://example.com"
  let courseRun: CourseRunDetail, user: LoggedInUser
  beforeEach(() => {
    courseRun = makeCourseRunDetail()
    user = makeUser()
  })
  describe("isLinkableCourseRun", () => {
    [
      [exampleUrl, past, future, false, "run is in progress", true],
      [
        exampleUrl,
        past,
        null,
        false,
        "run is in progress with no end date",
        true
      ],
      [
        exampleUrl,
        future,
        farFuture,
        true,
        "logged-in user is an editor",
        true
      ],
      [null, past, future, true, "run has an empty courseware url", false],
      [exampleUrl, future, null, false, "run is not in progress", false]
    ].forEach(
      ([coursewareUrl, startDate, endDate, isEditor, desc, expLinkable]) => {
        it(`returns ${String(expLinkable)} when ${desc}`, () => {
          courseRun.courseware_url = coursewareUrl as string | null
          courseRun.start_date = startDate as string | null
          courseRun.end_date = endDate as string | null
          user.is_editor = isEditor as boolean
          assert.equal(isLinkableCourseRun(courseRun, user), expLinkable)
        })
      }
    )
  })
  describe("isWithinEnrollmentPeriod", () => {
    [
      [past, future, "active enrollment period", true],
      [past, null, "active enrollment period with no end", true],
      [null, null, "null enrollment start", false],
      [farPast, past, "past enrollment period", false],
      [future, farFuture, "future enrollment period", false]
    ].forEach(([enrollStart, enrollEnd, desc, expResult]) => {
      it(`returns ${String(expResult)} with ${desc}`, () => {
        courseRun.enrollment_start = enrollStart as string | null
        courseRun.enrollment_end = enrollEnd as string | null
        assert.equal(isWithinEnrollmentPeriod(courseRun), expResult)
      })
    })
  })
})
