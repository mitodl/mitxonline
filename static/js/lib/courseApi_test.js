/* global SETTINGS: false */
// @flow
import { isLinkableCourseRun } from "./courseApi"
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
})
