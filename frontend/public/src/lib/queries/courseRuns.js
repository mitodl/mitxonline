import { pathOr } from "ramda"

import { nextState } from "./util"

export const courseRunsSelector = pathOr(null, ["entities", "courseRuns"])
export const coursesSelector = pathOr(null, ["entities", "courses"])

export const courseRunsQueryKey = "courseRuns"
export const coursesQueryKey = "courses"

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

export const coursesQuery = (courseKey: string = "") => ({
  queryKey:  coursesQueryKey,
  url:       `/api/courses/?readable_id=${encodeURIComponent(courseKey)}`,
  transform: json => ({
    courses: json
  }),
  update: {
    courses: nextState
  }
})
