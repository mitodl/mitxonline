import { compose, createStore, applyMiddleware } from "redux"
import { createLogger } from "redux-logger"
import { queryMiddleware } from "redux-query"

import { makeRequest } from "./network_interface"
import rootReducer from "../reducers"

// Setup middleware
export default function configureStore(initialState: Object) {
  const getQueries = state => state.queries
  const getEntities = state => state.entities
  const COMMON_MIDDLEWARE = [
    queryMiddleware(makeRequest, getQueries, getEntities)
  ]

  // Store factory configuration
  let createStoreWithMiddleware
  if (process.env.NODE_ENV !== "production" && !global.TESTING) {
    createStoreWithMiddleware = compose(
      applyMiddleware(...COMMON_MIDDLEWARE, createLogger()),
      window.__REDUX_DEVTOOLS_EXTENSION__
        ? window.__REDUX_DEVTOOLS_EXTENSION__()
        : f => f
    )(createStore)
  } else {
    createStoreWithMiddleware = compose(applyMiddleware(...COMMON_MIDDLEWARE))(
      createStore
    )
  }

  const store = createStoreWithMiddleware(rootReducer, initialState)

  if (module.hot) {
    // Enable Webpack hot module replacement for reducers
    module.hot.accept("../reducers", () => {
      const nextRootReducer = require("../reducers")

      store.replaceReducer(nextRootReducer)
    })
  }

  return store
}
