// @flow
import { nthArg } from "ramda"

import { getCookie } from "../api"

import type { QueryState } from "redux-query"

// replace the previous state with the next state without merging
export const nextState = nthArg(1)

export const hasUnauthorizedResponse = (queryState: ?QueryState) =>
  queryState &&
  queryState.isFinished &&
  (queryState.status === 401 || queryState.status === 403)

export const getCsrfOptions = () => ({
  headers: {
    "X-CSRFTOKEN": getCookie("csrftoken")
  }
})

export const getQueries = (state: Object) => state.queries
export const getEntities = (state: Object) => state.entities
