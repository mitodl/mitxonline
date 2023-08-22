import { pathOr } from "ramda"

import { nextState } from "./util"

export const coursesSelector = pathOr(null, ["entities", "courses", "results"])

export const coursesNextPageSelector = pathOr(null, [
  "entities",
  "courses",
  "next"
])

export const coursesQueryKey = "courses"

export const coursesQuery = page => ({
  queryKey:  coursesQueryKey,
  url:       `/api/courses/?page=${page}`,
  transform: json => ({
    courses: json
  }),
  update: {
    courses: nextState
  }
})
