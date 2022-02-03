import { createBrowserHistory } from "history"
import React from "react"
import ReactDOM from "react-dom"
import { AppContainer } from "react-hot-loader"
import { Provider } from "react-redux"
import { Router as ReactRouter } from "react-router"
import HeaderApp from "../containers/HeaderApp"
import ProductDetailEnrollApp from "../containers/ProductDetailEnrollApp"
import { AppTypeContext, MIXED_APP_CONTEXT } from "../contextDefinitions"
import { NotificationsProvider } from "../hooks/notifications"
import configureStore, { Store } from "../store/configureStore"

require("react-hot-loader/patch")

/* global SETTINGS:false */
__webpack_public_path__ = SETTINGS.public_path // eslint-disable-line no-undef, camelcase

const store = configureStore()
const rootEl = document.getElementById("header")

const renderHeader = () => {
  const history = createBrowserHistory()
  ReactDOM.render(
    <AppContainer>
      <Provider store={store}>
        <AppTypeContext.Provider value={MIXED_APP_CONTEXT}>
          <NotificationsProvider>
            <ReactRouter history={history}>
              <HeaderApp />
            </ReactRouter>
          </NotificationsProvider>
        </AppTypeContext.Provider>
      </Provider>
    </AppContainer>,
    rootEl
  )
}

const renderEnrollSection = (
  courseId: string,
  element: HTMLElement,
  reduxStore: Store
) => {
  ReactDOM.render(
    <AppContainer>
      <Provider store={reduxStore}>
        <NotificationsProvider>
          <ProductDetailEnrollApp courseId={courseId} />
        </NotificationsProvider>
      </Provider>
    </AppContainer>,
    element
  )
}

renderHeader()
document.addEventListener("DOMContentLoaded", function() {
  const enrollSectionEl = document.getElementById("productDetailEnrollment")
  const courseIdEl = document.getElementById(
    "courseId"
  ) as HTMLInputElement | null

  if (enrollSectionEl && courseIdEl) {
    const productDetailStore = configureStore()
    const courseId = courseIdEl.value
    renderEnrollSection(courseId, enrollSectionEl, productDetailStore)
  }
})
