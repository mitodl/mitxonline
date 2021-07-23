import { pathOr } from "ramda"

import { nextState } from "./util"

export const enrollmentsSelector = pathOr(null, ["entities", "enrollments"])

export const enrollmentsQuery = () => ({
  url:       "/api/enrollments/",
  transform: json => ({
    enrollments: json
  }),
  update: {
    enrollments: nextState
  }
})
