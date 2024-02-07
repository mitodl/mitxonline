import { pathOr } from "ramda"

import { nextState } from "./util"
import { PAGE_SIZE } from "../../constants"

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

export const coursesQuery = page => ({
  queryKey:  coursesQueryKey,
  url:       `/api/v2/courses/?page=${page}&live=true&page__live=true&courserun_is_enrollable=true&page_size=${PAGE_SIZE}`,
  transform: json => ({
    courses: json
  }),
  update: {
    courses: (prev, next) => ({...prev, ...next})
  },
  force: true,
})
