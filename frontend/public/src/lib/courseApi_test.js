// @flow
import {
  isLinkableCourseRun,
  isWithinEnrollmentPeriod,
  generateStartDateText, isFinancialAssistanceAvailable
} from "./courseApi"
import { assert } from "chai"
import moment from "moment"

import { makeCourseRunDetail } from "../factories/course"
import { makeUser } from "../factories/user"

import type { CourseRunDetail } from "../flow/courseTypes"
import type { LoggedInUser } from "../flow/authTypes"

describe("Course API", () => {
  const past = moment()
      .add(-10, "days")
      .toISOString(),
    farPast = moment()
      .add(-50, "days")
      .toISOString(),
    future = moment()
      .add(10, "days")
      .toISOString(),
    farFuture = moment()
      .add(50, "days")
      .toISOString(),
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
          courseRun.courseware_url = coursewareUrl
          courseRun.start_date = startDate
          courseRun.end_date = endDate
          user.is_editor = isEditor
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
        courseRun.enrollment_start = enrollStart
        courseRun.enrollment_end = enrollEnd
        assert.equal(isWithinEnrollmentPeriod(courseRun), expResult)
      })
    })
  })

  describe("generateStartDateText", () => {
    [
      [
        exampleUrl,
        past,
        future,
        "run is in progress",
        { active: true, datestr: "" }
      ],
      [
        exampleUrl,
        past,
        null,
        "run is in progress with no end date",
        { active: true, datestr: "" }
      ],
      [
        exampleUrl,
        future,
        null,
        "run is not in progress",
        { active: true, datestr: "" }
      ],
      [exampleUrl, null, null, "run has no start date", null]
    ].forEach(([coursewareUrl, startDate, endDate, desc, expLinkable]) => {
      it(`returns ${String(expLinkable)} when ${desc}`, () => {
        courseRun.courseware_url = coursewareUrl
        courseRun.start_date = startDate
        courseRun.end_date = endDate
        assert.equal(
          typeof generateStartDateText(courseRun),
          typeof expLinkable
        )
      })
    })
  })

  describe("isFinancialAssistanceAvailable", () => {
    [
      ["", false],
      [null, false],
      ["/courses/course-v1:MITx+14.310x/financial-assistance-request/", true],
    ].forEach(([url, expResult]) => {
      it(`returns ${String(expResult)}`, () => {
        courseRun["page"] = {financial_assistance_form_url: url}
        assert.equal(isFinancialAssistanceAvailable(courseRun), expResult)
      })
    })
  })
})
