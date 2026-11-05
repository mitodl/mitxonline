import { compose, createStore, applyMiddleware } from "redux"
import { createLogger } from "redux-logger"
import { queryMiddleware } from "redux-query"

import { makeRequest } from "./network_interface"
import rootReducer from "../reducers"
import { getEntities, getQueries } from "../lib/queries/util"
import posthogIdentifyMiddleware from "./posthogIdentify"

// Setup middleware
export default function configureStore(initialState: Object) {
  const COMMON_MIDDLEWARE = [
    queryMiddleware(
      makeRequest,
      getQueries,
      getEntities,
      // A retry is a timer that outlives the test that started it and fires
      // into whichever test runs next, so tests don't retry.
      global.TESTING ? { retryableStatusCodes: [] } : undefined
    ),
    posthogIdentifyMiddleware
  ]

  // Store factory configuration
  let createStoreWithMiddleware
  if (process.env.NODE_ENV !== "production" && !global.TESTING) {
    createStoreWithMiddleware = compose(
      applyMiddleware(...COMMON_MIDDLEWARE, createLogger()),
      window.__REDUX_DEVTOOLS_EXTENSION__ ?
        window.__REDUX_DEVTOOLS_EXTENSION__() :
        f => f
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
