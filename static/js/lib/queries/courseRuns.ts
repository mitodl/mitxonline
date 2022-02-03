import { pathOr } from "ramda"
import { EnrollmentFlaggedCourseRun } from "../../types/course"
import { nextState } from "./util"

export const courseRunsQueryKey = "courseRuns"
export const courseRunsSelector = pathOr<EnrollmentFlaggedCourseRun[] | null>(
  null,
  ["entities", courseRunsQueryKey]
)
export const courseRunsQuery = (courseKey = "") => ({
  queryKey:  courseRunsQueryKey,
  url:       `/api/course_runs/?relevant_to=${encodeURIComponent(courseKey)}`,
  transform: (courseRuns: EnrollmentFlaggedCourseRun[]) => ({ courseRuns }),
  update:    {
    courseRuns: nextState
  }
})
