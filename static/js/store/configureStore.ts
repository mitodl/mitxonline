import { applyMiddleware, compose, createStore } from "redux"
import { createLogger } from "redux-logger"
import { queryMiddleware } from "redux-query"
import { getEntities, getQueries } from "../lib/redux_query"
import rootReducer, { ReduxState } from "../reducers"
import { makeRequest } from "./network_interface"

export type Store = ReturnType<typeof configureStore>

// Setup middleware
// eslint-disable-next-line @typescript-eslint/explicit-module-boundary-types
export default function configureStore(initialState?: Partial<ReduxState>) {
  const COMMON_MIDDLEWARE = [
    queryMiddleware(makeRequest, getQueries, getEntities)
  ]

  // Store factory configuration
  let createStoreWithMiddleware
  if (process.env.NODE_ENV !== "production" && !globalThis._testing) {
    createStoreWithMiddleware = compose(
      applyMiddleware(...COMMON_MIDDLEWARE, createLogger()),
      window.__REDUX_DEVTOOLS_EXTENSION__
        ? window.__REDUX_DEVTOOLS_EXTENSION__()
        : (f: any) => f
      // @ts-ignore
    )(createStore)
  } else {
    createStoreWithMiddleware = compose(applyMiddleware(...COMMON_MIDDLEWARE))(
      createStore
    )
  }

  const store = createStoreWithMiddleware(rootReducer, initialState)

  if ((module as any).hot) {
    // Enable Webpack hot module replacement for reducers
    (module as any).hot.accept("../reducers", () => {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const nextRootReducer = require("../reducers")

      store.replaceReducer(nextRootReducer)
    })
  }

  return store
}
