import React from "react"
import R from "ramda"
import {mount, shallow} from "enzyme"
import sinon from "sinon"
import { createMemoryHistory } from "history"

import configureStoreMain from "../store/configureStore"

import type { Sandbox } from "../flow/sinonTypes"
import * as networkInterfaceFuncs from "../store/network_interface"
import {Provider} from "react-redux"
import {Route, Router} from "react-router"

export default class IntegrationTestHelper {
  sandbox: Sandbox
  browserHistory: History
  actions: Array<any>

  constructor() {
    this.sandbox = sinon.createSandbox({})
    this.actions = []

    this.scrollIntoViewStub = this.sandbox.stub()
    window.HTMLDivElement.prototype.scrollIntoView = this.scrollIntoViewStub
    window.HTMLFieldSetElement.prototype.scrollIntoView = this.scrollIntoViewStub
    this.browserHistory = createMemoryHistory()
    this.currentLocation = null
    this.browserHistory.listen(url => {
      this.currentLocation = url
    })

    const defaultResponse = {
      body:   {},
      status: 200
    }
    this.handleRequestStub = this.sandbox.stub().returns(defaultResponse)
    this.sandbox
      .stub(networkInterfaceFuncs, "makeRequest")
      .callsFake((url, method, options) => ({
        execute: callback => {
          const response = this.handleRequestStub(url, method, options)
          const err = null
          const resStatus = (response && response.status) || 0
          const resBody = (response && response.body) || undefined
          const resText = (response && response.text) || undefined
          const resHeaders = (response && response.header) || undefined

          callback(err, resStatus, resBody, resText, resHeaders)
        },
        abort: () => {
          throw new Error("Aborts currently unhandled")
        }
      }))
  }

  cleanup() {
    this.actions = []
    this.sandbox.restore()
  }

  configureShallowRenderer(
    WrappedComponent: Class<React.Component<*, *>>,
    InnerComponent: Class<React.Component<*, *>>,
    defaultState: Object,
    defaultProps = {}
  ) {
    const history = this.browserHistory
    return async (extraState = {}, extraProps = {}) => {
      const initialState = R.mergeDeepRight(defaultState, extraState)
      const store = configureStoreMain(initialState)
      const wrapper = await shallow(
        <InnerComponent
          store={store}
          dispatch={store.dispatch}
          history={history}
          {...defaultProps}
          {...extraProps}
        />,
        {
          context: {
            // TODO: should be removed in the near future after upgrading enzyme
            store
          }
        }
      )

      // just a little convenience method
      store.getLastAction = function() {
        const actions = this.getActions()
        return actions[actions.length - 1]
      }

      // dive through layers of HOCs until we reach the desired inner component
      const inner = wrapper

      console.log(inner)
      return { wrapper, inner, store }
    }
  }

  configureMountRenderer(
    WrappedComponent: Class<React.Component<*, *>>,
    InnerComponent: Class<React.Component<*, *>>,
    defaultState: Object,
    defaultProps = {}
  ) {
    const history = this.browserHistory
    return async (
      extraState = {},
      extraProps = {}
    ) => {
      const initialState = R.mergeDeepRight(defaultState, extraState)
      const store = configureStoreMain(initialState)

      console.log(InnerComponent)
      const ComponentWithProps = () => (
        <WrappedComponent
          {...defaultProps}
          {...extraProps}
        />
      )

      console.log(ComponentWithProps)

      const wrapper = mount(
        <Provider store={store}>
          <Router history={history}>
            <Route path="*" component={ComponentWithProps} />
          </Router>
        </Provider>,
      )
      store.getLastAction = function() {
        const actions = this.getActions()
        return actions[actions.length - 1]
      }

      const inner = wrapper.find(InnerComponent)

      return { inner, wrapper, store }
    }
  }
}
