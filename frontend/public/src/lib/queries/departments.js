import { pathOr } from "ramda"

import { nextState } from "./util"

export const departmentsSelector = pathOr(null, ["entities", "departments"])

export const departmentsQueryKey = "departments"

export const departmentsQuery = () => ({
  queryKey:  departmentsQueryKey,
  url:       `/api/v2/departments`,
  transform: json => ({
    departments: json.results
  }),
  update: {
    departments: nextState
  }
})
