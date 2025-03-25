import { pathOr } from "ramda"

import { nextState } from "./util"

export const courseRunsSelector = pathOr(null, ["entities", "courseRuns"])
export const coursesSelector = pathOr(null, ["entities", "courses"])
export const programsSelector = pathOr(null, ["entities", "programs"])

export const courseRunsQueryKey = "courseRuns"
export const coursesQueryKey = "courses"
export const programsQueryKey = "programs"

export const courseRunsQuery = (courseKey: string = "") => ({
  queryKey:  courseRunsQueryKey,
  url:       `/api/v1/course_runs/?relevant_to=${encodeURIComponent(courseKey)}`,
  transform: json => ({
    courseRuns: json
  }),
  update: {
    courseRuns: nextState
  }
})

export const coursesQuery = (courseKey: string = "") => ({
  queryKey: coursesQueryKey,
  url:      `/api/v1/courses/?readable_id=${encodeURIComponent(
    courseKey
  )}&live=true`,
  transform: json => ({
    courses: json
  }),
  update: {
    courses: nextState
  }
})

// This will need to be updated to v2 once we get the courses endpoint to allow for multiple ID query
export const programsQuery = (programKey: string = "") => ({
  queryKey:  programsQueryKey,
  url:       `/api/v1/programs/?readable_id=${encodeURIComponent(programKey)}`,
  transform: json => ({
    programs: json
  }),
  update: {
    programs: nextState
  }
})
