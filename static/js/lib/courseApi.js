// @flow
/* global SETTINGS:false */
import moment from "moment"
import { isNil } from "ramda"
import { notNil } from "./util"

import type Moment from "moment"
import type { RunEnrollment } from "../flow/courseTypes"

export const isLinkableCourseRun = (
  run: RunEnrollment,
  dtNow?: Moment
): boolean => {
  const now = dtNow || moment()
  return (
    notNil(run.courseware_url) &&
    notNil(run.start_date) &&
    moment(run.start_date).isBefore(now) &&
    (isNil(run.end_date) || moment(run.end_date).isAfter(now))
  )
}
