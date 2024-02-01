import { pathOr } from "ramda"

import { nextState } from "./util"
import { PAGE_SIZE } from "../../constants"

export const departmentsSelector = pathOr(null, [
  "entities",
  "departments",
  "results"
])
export const departmentsCountSelector = pathOr(null, [
  "entities",
  "departments",
  "count"
])
export const departmentsNextPageSelector = pathOr(null, [
  "entities",
  "departments",
  "next"
])

export const departmentsQueryKey = "departments"

export const departmentsQuery = page => ({
  queryKey:  departmentsQueryKey,
  url:       `/api/v2/departments/?page=${page}&page_size=${PAGE_SIZE}`,
  transform: json => ({
    departments: json
  }),
  update: {
    departments: nextState
  }
})
