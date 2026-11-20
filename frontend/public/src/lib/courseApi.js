// @flow
import React from "react"
import moment from "moment"

import { parseDateString, formatPrettyDateTimeAmPmTz } from "./util"

import { NODETYPE_OPERATOR, NODETYPE_COURSE, NODEOPER_ALL } from "../constants"

import type {
  CourseRunDetail,
  CourseRun,
  CourseDetail,
  RequirementNode,
  LearnerRecord,
  ProgramRequirement
} from "../flow/courseTypes"

export const courseRunStatusMessage = (run: CourseRun) => {
  const startDateDescription = generateStartDateText(run)
  if (startDateDescription !== null) {
    if (startDateDescription.active) {
      return (
        <span>
          {" "}
          |<strong className="active-enrollment-text"> Active</strong> from{" "}
          {startDateDescription.datestr}
        </span>
      )
    } else {
      if (run.end_date !== null && moment(run.end_date).isBefore(moment())) {
        const dateString = parseDateString(run.end_date)
        return (
          <span>
            {" "}
            | <strong>Ended</strong> {formatPrettyDateTimeAmPmTz(dateString)}
          </span>
        )
      } else {
        return (
          <span>
            {" "}
            | <strong className="text-dark">Starts</strong>{" "}
            {startDateDescription.datestr}
          </span>
        )
      }
    }
  } else {
    return null
  }
}

export const generateStartDateText = (run: CourseRunDetail) => {
  if (run.start_date) {
    const now = moment()
    const startDate = parseDateString(run.start_date)
    const formattedStartDate = formatPrettyDateTimeAmPmTz(startDate)
    if (run.end_date) {
      const endDate = parseDateString(run.end_date)
      return now.isAfter(startDate) && now.isBefore(endDate) ?
        { active: true, datestr: formattedStartDate } :
        { active: false, datestr: formattedStartDate }
    } else {
      return now.isAfter(startDate) ?
        { active: true, datestr: formattedStartDate } :
        { active: false, datestr: formattedStartDate }
    }
  }

  return null
}

export const isFinancialAssistanceAvailable = (run: CourseRunDetail) => {
  return run.course.page ?
    !!run.course.page.financial_assistance_form_url :
    false
}

const isNodeCompleted = (
  node: RequirementNode,
  learnerRecord: LearnerRecord
) => {
  // Determines if the node itself is complete using the rules above

  if (node.node_type !== NODETYPE_COURSE) {
    return true
  }

  const course = learnerRecord.program.courses.find(
    course => course.id === node.course
  )

  return course && course.grade && course.certificate
}

export const walkNodes = (
  node: ProgramRequirement,
  learnerRecord: LearnerRecord
) => {
  // Processes the node. if the node is an operator, roll through each child
  // node and recurse. If the node is a course, check if it's completed.
  if (node) {
    if (node.data.node_type === NODETYPE_OPERATOR) {
      let completedCount = 0

      if (node.children) {
        node.children.forEach(child => {
          completedCount += walkNodes(child, learnerRecord)
        })

        if (node.data.operator === NODEOPER_ALL) {
          return completedCount === node.children.length ? 1 : 0
        } else {
          return completedCount >= parseInt(node.data.operator_value) ? 1 : 0
        }
      }
    } else if (node.data.node_type === NODETYPE_COURSE) {
      return isNodeCompleted(node.data, learnerRecord) ? 1 : 0
    }
  }

  return false
}

export const learnerProgramIsCompleted = (learnerRecord: LearnerRecord) => {
  /*
    Checks to see if the learner has completed the program they're in. This
    is for use with learner records.

    A program is completed if:
    * It has requirements
    * All of the requirements listed in the Required Courses node are done
    * The Electives (if there are any) are also done

    A course is completed if:
    * It has a grade
    * A certificate has been issued for the course
  */

  if (!learnerRecord || learnerRecord.program.requirements.length === 0) {
    return false
  }

  const requiredCourses = learnerRecord.program.requirements[0].children[0]
  const electiveCourses = learnerRecord.program.requirements[0].children[1]

  const requirementsDone = walkNodes(requiredCourses, learnerRecord)
  if (electiveCourses) {
    const electivesDone = walkNodes(electiveCourses, learnerRecord)
    return requirementsDone && electivesDone
  }
  return !!requirementsDone
}

export const getFirstRelevantRun = (
  course: CourseDetail,
  courseRuns: Array<CourseRunDetail>
) => {
  /*
   Finds the next most relevant course run:
   - If the course has a next_run_id, return that run
   - If there are no runs, return null

   Args:
   course: CourseDetail - the course itself
   courseRuns: Array<CourseRunDetail> - the course runs to search

   Returns: CourseRunDetail
  */

  if (
    course.courseruns.length === 0 ||
    courseRuns === null ||
    courseRuns.length === 0
  ) {
    return null
  }

  if (course.next_run_id) {
    return courseRuns.find(run => run.id === course.next_run_id)
  }
  return null
}
