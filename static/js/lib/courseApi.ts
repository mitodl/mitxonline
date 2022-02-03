import moment, { Moment } from "moment"
import { isNil } from "ramda"
import { CurrentUser } from "../types/auth"
import { BaseCourseRun } from "../types/course"
import { notNil } from "./util"

export const isLinkableCourseRun = (
  run: BaseCourseRun,
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

export const isWithinEnrollmentPeriod = (run: BaseCourseRun): boolean => {
  const enrollStart = run.enrollment_start ? moment(run.enrollment_start) : null
  const enrollEnd = run.enrollment_end ? moment(run.enrollment_end) : null
  const now = moment()
  return (
    !!enrollStart &&
    now.isAfter(enrollStart) &&
    (isNil(enrollEnd) || now.isBefore(enrollEnd))
  )
}
