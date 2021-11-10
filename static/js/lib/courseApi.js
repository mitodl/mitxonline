// @flow
/* global SETTINGS:false */
import moment from "moment"
import { isNil } from "ramda"

import { notNil } from "./util"

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
  return (
    notNil(run.start_date) &&
    moment(run.start_date).isBefore(now) &&
    (isNil(run.end_date) || moment(run.end_date).isAfter(now))
  )
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
