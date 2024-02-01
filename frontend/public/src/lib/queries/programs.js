import { pathOr } from "ramda"

import { nextState } from "./util"
import { PAGE_SIZE } from "../../constants"

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

export const programsCountSelector = pathOr(null, [
  "entities",
  "programs",
  "count"
])

export const programsQueryKey = "programs"

export const programsQuery = page => ({
  queryKey:  programsQueryKey,
  url:       `/api/v2/programs/?page=${page}&live=true&page__live=true&page_size=${PAGE_SIZE}`,
  transform: json => ({
    programs: json
  }),
  update: {
    programs: nextState
  }
})
