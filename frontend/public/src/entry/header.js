import "core-js/stable"
import "regenerator-runtime/runtime"
import React from "react"
import ReactDOM from "react-dom"
import { Provider } from "react-redux"
import { AppContainer } from "react-hot-loader"
import { Router as ReactRouter } from "react-router"
import { createBrowserHistory } from "history"

import configureStore from "../store/configureStore"
import { AppTypeContext, MIXED_APP_CONTEXT } from "../contextDefinitions"
import HeaderApp from "../containers/HeaderApp"
import ProductDetailEnrollApp from "../containers/ProductDetailEnrollApp"
// Object.entries polyfill
import entries from "object.entries"

if (!Object.entries) {
  entries.shim()
}

const store = configureStore()

const rootEl = document.getElementById("header")

const renderHeader = () => {
  const history = createBrowserHistory()
  ReactDOM.render(
    <AppContainer>
      <Provider store={store}>
        <AppTypeContext.Provider value={MIXED_APP_CONTEXT}>
          <ReactRouter history={history}>
            <HeaderApp />
          </ReactRouter>
        </AppTypeContext.Provider>
      </Provider>
    </AppContainer>,
    rootEl
  )
}

const renderEnrollSection = (
  courseId,
  programId,
  userId,
  element,
  reduxStore
) => {
  ReactDOM.render(
    <AppContainer>
      <Provider store={reduxStore}>
        <ProductDetailEnrollApp
          courseId={courseId}
          programId={programId}
          userId={userId}
        />
      </Provider>
    </AppContainer>,
    element
  )
}

renderHeader()

document.addEventListener("DOMContentLoaded", function() {
  const enrollSectionEl = document.getElementById("productDetailEnrollment")
  const courseIdEl = document.getElementById("courseId")
  const programIdEl = document.getElementById("programId")
  const userIdEl = document.getElementById("userId")
  if (enrollSectionEl && (programIdEl || courseIdEl)) {
    const productDetailStore = configureStore()
    const courseId = courseIdEl ? courseIdEl.value : undefined
    const programId = programIdEl ? programIdEl.value : undefined
    const userId = userIdEl ? userIdEl.value : undefined
    renderEnrollSection(
      courseId,
      programId,
      userId,
      enrollSectionEl,
      productDetailStore
    )
  }
})
