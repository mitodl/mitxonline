// @flow
/* global SETTINGS:false */
import React from "react"
import moment from "moment"
import { isNil } from "ramda"

import { notNil, parseDateString, formatPrettyDateTimeAmPmTz } from "./util"

import type Moment from "moment"
import type { CourseRunDetail } from "../flow/courseTypes"
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
