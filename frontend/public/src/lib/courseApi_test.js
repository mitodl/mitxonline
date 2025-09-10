// @flow
import {
  isLinkableCourseRun,
  generateStartDateText,
  isFinancialAssistanceAvailable,
  learnerProgramIsCompleted,
  extractCoursesFromNode,
  walkNodes,
  getFirstRelevantRun
} from "./courseApi"
import { assert } from "chai"
import moment from "moment"

import {
  makeCourseRunDetail,
  makeLearnerRecord,
  makeProgramWithReqTree,
  makeProgramWithOnlyRequirements,
  makeProgramWithOnlyElectives,
  makeProgramWithNoElectivesOrRequirements,
  makeProgram,
  makeCourseDetailWithRuns
} from "../factories/course"
import { makeUser } from "../factories/user"

import type { CourseRunDetail } from "../flow/courseTypes"
import type { LoggedInUser } from "../flow/authTypes"

describe("Course API", () => {
  const past = moment().add(-10, "days").toISOString(),
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
          courseRun.courseware_url = coursewareUrl
          courseRun.start_date = startDate
          courseRun.end_date = endDate
          user.is_editor = isEditor
          assert.equal(isLinkableCourseRun(courseRun, user), expLinkable)
        })
      }
    )
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

  describe("extractCoursesFromNode", () => {
    it("returns a flattened list of courses for the node", () => {
      // the learner record will generate a requirements tree in the proper
      // format, so we're just using that factory here
      const programEnrollment = {
        program:     makeProgramWithReqTree(),
        enrollments: []
      }

      const requirements = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[0],
        programEnrollment
      )
      const electives = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[1],
        programEnrollment
      )

      assert.equal(requirements.length, 3)
      assert.equal(electives.length, 4)
    })

    it("returns a flattened list of courses for the node without any elective courses", () => {
      // the learner record will generate a requirements tree in the proper
      // format, so we're just using that factory here
      const programEnrollment = {
        program:     makeProgramWithOnlyRequirements(),
        enrollments: []
      }

      const requirements = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[0],
        programEnrollment
      )
      const electives = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[1],
        programEnrollment
      )

      assert.equal(requirements.length, 3)
      assert.equal(electives.length, 0)
    })

    it("returns a flattened list of courses for the node without any required courses", () => {
      // the learner record will generate a requirements tree in the proper
      // format, so we're just using that factory here
      const programEnrollment = {
        program:     makeProgramWithOnlyElectives(),
        enrollments: []
      }

      const requirements = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[0],
        programEnrollment
      )
      const electives = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[1],
        programEnrollment
      )

      assert.equal(requirements.length, 0)
      assert.equal(electives.length, 4)
    })

    it("returns a flattened list of courses for the node without any required courses or elective courses", () => {
      // the learner record will generate a requirements tree in the proper
      // format, so we're just using that factory here
      const programEnrollment = {
        program:     makeProgramWithNoElectivesOrRequirements(),
        enrollments: []
      }

      const requirements = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[0],
        programEnrollment
      )
      const electives = extractCoursesFromNode(
        programEnrollment.program.req_tree[0].children[1],
        programEnrollment
      )

      assert.equal(requirements.length, 0)
      assert.equal(electives.length, 0)
    })

    it("returns a flattened list of courses associated with the program without nodes", () => {
      // the learner record will generate a requirements tree in the proper
      // format, so we're just using that factory here
      const programEnrollment = {
        program:     makeProgram(),
        enrollments: []
      }

      // Pass undefined which can occur when an admin user deletes the requirement or elective sections from the program record.
      const requirements = extractCoursesFromNode(undefined, programEnrollment)
      const electives = extractCoursesFromNode(undefined, programEnrollment)

      assert.equal(requirements.length, 0)
      assert.equal(electives.length, 0)
    })
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
