import { combineReducers } from "redux"
import {
  entitiesReducer,
  EntitiesState,
  queriesReducer,
  QueriesState
} from "redux-query"

export type ReduxState = {
  entities: EntitiesState
  queries: QueriesState
}

export default combineReducers<ReduxState>({
  entities: entitiesReducer,
  queries:  queriesReducer
})
