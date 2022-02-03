import Cookies from "js-cookie"
import { nthArg } from "ramda"
import { QueryState } from "redux-query"

// replace the previous state with the next state without merging
export const nextState = nthArg(1)
export const hasUnauthorizedResponse = (
  queryState: QueryState | null | undefined
) =>
  queryState &&
  queryState.isFinished &&
  (queryState.status === 401 || queryState.status === 403)

export const getCsrfOptions = () => ({
  headers: {
    "X-CSRFTOKEN": Cookies.get("csrftoken") || ""
  }
})
