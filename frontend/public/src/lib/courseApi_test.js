// @flow
import {
  generateStartDateText,
  isFinancialAssistanceAvailable,
  learnerProgramIsCompleted,
  walkNodes,
  getFirstRelevantRun
} from "./courseApi"
import { assert } from "chai"
import moment from "moment"

import {
  makeCourseRunDetail,
  makeLearnerRecord,
  makeCourseDetailWithRuns
} from "../factories/course"

import type { CourseRunDetail } from "../flow/courseTypes"

describe("Course API", () => {
  const past = moment().add(-10, "days").toISOString(),
    future = moment().add(10, "days").toISOString(),
    exampleUrl = "http://example.com"
  let courseRun: CourseRunDetail

  beforeEach(() => {
    courseRun = makeCourseRunDetail()
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
        { active: false, datestr: "" }
      ],
      [
        exampleUrl,
        past,
        past,
        "run is not in progress",
        { active: false, datestr: "" }
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
      ["/courses/course-v1:MITx+14.310x/financial-assistance-request/", true]
    ].forEach(([url, expResult]) => {
      it(`returns ${String(expResult)}`, () => {
        courseRun["course"]["page"] = { financial_assistance_form_url: url }
        assert.equal(isFinancialAssistanceAvailable(courseRun), expResult)
      })
    })
  })

  describe("learnerProgramIsCompleted", () => {
    [
      [true, "returns true", "all courses are complete", "has electives"],
      [
        false,
        "returns false",
        "not enough courses are complete",
        "no electives"
      ],
      [
        true,
        "returns true",
        "all courses are complete",
        "does not have electives"
      ]
    ].forEach(
      ([shouldBeCompleted, returnResult, courseConditions, hasElectives]) => {
        it(`${returnResult} when ${courseConditions} and ${hasElectives}`, () => {
          const learnerRecord = makeLearnerRecord(shouldBeCompleted)

          if (hasElectives === "does not have electives") {
            learnerRecord.program.requirements[0].children[1] = undefined
          }
          if (shouldBeCompleted) {
            assert.isOk(learnerProgramIsCompleted(learnerRecord))
          } else {
            if (courseConditions === "not enough courses are complete") {
              // force one of the required courses to be incomplete
              learnerRecord.program.courses[0].certificate = null
              learnerRecord.program.courses[0].grade = null
              assert.isNotOk(learnerProgramIsCompleted(learnerRecord))
            }
          }
        })
      }
    )
  })

  describe("walkNodes", () => {
    [
      [
        {
          data: {
            node_type:      "operator",
            operator:       "min_number_of",
            operator_value: "1",
            program:        2,
            course:         null,
            title:          "Elective Courses"
          },
          id: 13
        },
        false
      ],
      [undefined, false],
      [
        {
          data: {
            node_type:      "operator",
            operator:       "all_of",
            operator_value: "1",
            program:        2,
            course:         null,
            title:          "Required Courses"
          },
          id: 13
        },
        false
      ]
    ].forEach(([node, expResult]) => {
      it(`returns ${String(expResult)}`, () => {
        const learnerRecord = makeLearnerRecord(false)
        const result = walkNodes(node, learnerRecord)
        assert.equal(result, expResult)
      })
    })
  })

  describe("getFirstRelevantRun", () => {
    it("returns null if there aren't any supplied course runs", () => {
      const course = makeCourseDetailWithRuns()
      const result = getFirstRelevantRun(course, [])
      assert.equal(result, null)
    })

    it("returns null if next_run_id is not provided for the course", () => {
      const testCourse = {
        ...makeCourseDetailWithRuns(),
        courseruns: []
      }
      const result = getFirstRelevantRun(testCourse, [makeCourseRunDetail()])
      assert.equal(result, null)
    })
    it("returns next_run_id for the course", () => {
      const testCourse = makeCourseDetailWithRuns()
      const courseRun = testCourse.courseruns[0]
      testCourse.next_run_id = courseRun.id
      const result = getFirstRelevantRun(testCourse, [courseRun])
      assert.equal(result, courseRun)
    })
  })
})
