import { pathOr } from "ramda"

import { nextState } from "./util"

export const coursesSelector = pathOr(null, ["entities", "courses", "results"])

export const coursesCountSelector = pathOr(null, [
  "entities",
  "courses",
  "count"
])

export const coursesNextPageSelector = pathOr(null, [
  "entities",
  "courses",
  "next"
])

export const coursesQueryKey = "courses"

export const coursesQuery = (page, ids) => ({
  queryKey: coursesQueryKey,
  url:
    ids && ids.length > 0
      ? `/api/v2/coursesa/?page=${page}&live=true&page__live=true&courserun_is_enrollable=true&id=${ids}`
      : `/api/v2/courses/?page=${page}&live=true&page__live=true&courserun_is_enrollable=true`,
  transform: json => ({
    courses: json
  }),
  update: {
    courses: nextState
  }
})
