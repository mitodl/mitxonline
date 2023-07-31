import { pathOr } from "ramda"

import { nextState } from "./util"

export const coursesSelector = pathOr(null, ["entities", "courses"])

export const coursesQueryKey = "courses"

export const coursesQuery = () => ({
  queryKey:  coursesQueryKey,
  url:       `/api/courses/`,
  transform: json => ({
    courses: json
  }),
  update: {
    courses: nextState
  }
})
