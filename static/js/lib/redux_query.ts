import Cookies from "js-cookie"
import { Entities, QueriesState } from "redux-query"
import { ReduxState } from "../reducers"

export const DEFAULT_POST_OPTIONS = {
  headers: {
    "X-CSRFTOKEN": Cookies.get("csrftoken")
  }
}

export const getQueries = (state: ReduxState): QueriesState => state.queries
export const getEntities = (state: ReduxState): Entities => state.entities
