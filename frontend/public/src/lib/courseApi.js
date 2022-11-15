// @flow
import React from "react"
import moment from "moment"
import { isNil } from "ramda"

import { notNil, parseDateString, formatPrettyDateTimeAmPmTz } from "./util"

import type Moment from "moment"
import type {
  CourseRunDetail,
  CourseRun,
  RunEnrollment
} from "../flow/courseTypes"
import type { CurrentUser } from "../flow/authTypes"

export const isLinkableCourseRun = (
  run: CourseRunDetail,
  currentUser: CurrentUser,
  dtNow?: Moment
): boolean => {
  if (isNil(run.courseware_url)) {
    return false
  }
  if (!currentUser.is_anonymous && currentUser.is_editor) {
    return true
  }
  const now = dtNow || moment()
  return notNil(run.start_date) && moment(run.start_date).isBefore(now)
}

export const isWithinEnrollmentPeriod = (run: CourseRunDetail): boolean => {
  const enrollStart = run.enrollment_start ? moment(run.enrollment_start) : null
  const enrollEnd = run.enrollment_end ? moment(run.enrollment_end) : null
  const now = moment()
  return (
    !!enrollStart &&
    now.isAfter(enrollStart) &&
    (isNil(enrollEnd) || now.isBefore(enrollEnd))
  )
}

export const courseRunStatusMessage = (run: CourseRun) => {
  const startDateDescription = generateStartDateText(run)
  if (startDateDescription !== null) {
    if (startDateDescription.active) {
      if (moment(run.end_date).isBefore(moment())) {
        const dateString = parseDateString(run.end_date)
        return (
          <span>
            {" "}
            | <strong>Ended</strong> - {formatPrettyDateTimeAmPmTz(dateString)}
          </span>
        )
      } else {
        return (
          <span>
            {" "}
            |<strong className="active-enrollment-text">
              {" "}
              Active
            </strong> from {startDateDescription.datestr}
          </span>
        )
      }
    } else {
      return (
        <span>
          {" "}
          | <strong className="text-dark">Starts</strong>{" "}
          {startDateDescription.datestr}
        </span>
      )
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
    return now.isBefore(startDate)
      ? { active: false, datestr: formattedStartDate }
      : { active: true, datestr: formattedStartDate }
  }

  return null
}

export const isFinancialAssistanceAvailable = (run: CourseRunDetail) => {
  return run.page ? !!run.page.financial_assistance_form_url : false
}

export const enrollmentHasPassingGrade = (enrollment: RunEnrollment) => {
  if (enrollment.grades && enrollment.grades.length > 0) {
    for (let i = 0; i < enrollment.grades.length; i++) {
      if (enrollment.grades[i].passed) {
        return true
      }
    }
  }

  return false
}
