import { pathOr } from "ramda"

import { nextState } from "./util"

export const programsSelector = pathOr(null, ["entities", "programs"])

export const programsQueryKey = "programs"

export const programsQuery = () => ({
  queryKey:  programsQueryKey,
  url:       `/api/programs/`,
  transform: json => ({
    programs: json
  }),
  update: {
    programs: nextState
  }
})
