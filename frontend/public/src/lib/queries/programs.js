import { pathOr } from "ramda"

import { nextState } from "./util"

export const programsSelector = pathOr(null, [
  "entities",
  "programs",
  "results"
])

export const programsNextPageSelector = pathOr(null, [
  "entities",
  "programs",
  "next"
])

export const programsQueryKey = "programs"

export const programsQuery = page => ({
  queryKey:  programsQueryKey,
  url:       `/api/programs/?page=${page}`,
  transform: json => ({
    programs: json
  }),
  update: {
    programs: nextState
  }
})
