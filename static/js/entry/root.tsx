import * as Sentry from "@sentry/browser"
import { createBrowserHistory } from "history"
import React from "react"
import ReactDOM from "react-dom"
import { AppContainer } from "react-hot-loader"
import { AppTypeContext, SPA_APP_CONTEXT } from "../contextDefinitions"
import Router, { routes } from "../Router"
import configureStore, { Store } from "../store/configureStore"

require("react-hot-loader/patch")

/* global SETTINGS:false */
__webpack_public_path__ = SETTINGS.public_path // eslint-disable-line no-undef, camelcase

Sentry.init({
  dsn:         SETTINGS.sentry_dsn,
  release:     SETTINGS.release_version,
  environment: SETTINGS.environment
})

const store = configureStore()
const rootEl = document.getElementById("container")

const renderApp = (
  Component: React.ComponentType<{
    history: ReturnType<typeof createBrowserHistory>
    store: Store
    children: React.ReactNode
  }>
) => {
  const history = createBrowserHistory()
  ReactDOM.render(
    <AppContainer>
      <AppTypeContext.Provider value={SPA_APP_CONTEXT}>
        <Component history={history} store={store}>
          {routes}
        </Component>
      </AppTypeContext.Provider>
    </AppContainer>,
    rootEl
  )
}

renderApp(Router)

if (module.hot) {
  module.hot.accept("../Router", () => {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const RouterNext = require("../Router").default

    renderApp(RouterNext)
  })
}
