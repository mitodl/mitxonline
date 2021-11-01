import { pathOr } from "ramda"

import { nextState } from "./util"

export const courseRunsSelector = pathOr(null, ["entities", "courseRuns"])

export const courseRunsQueryKey = "courseRuns"

export const courseRunsQuery = (courseKey: string = "") => ({
  queryKey:  courseRunsQueryKey,
  url:       `/api/course_runs/?relevant_to=${encodeURIComponent(courseKey)}`,
  transform: json => ({
    courseRuns: json
  }),
  update: {
    courseRuns: nextState
  }
})
