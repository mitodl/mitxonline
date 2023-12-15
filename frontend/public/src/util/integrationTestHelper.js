import React from "react"
import type {Sandbox} from "../flow/sinonTypes"
import sinon from "sinon"
import {createMemoryHistory} from "history"
import * as networkInterfaceFuncs from "../store/network_interface"
import R from "ramda"
import configureStoreMain from "../store/configureStore"
import {mount, shallow} from "enzyme"
import {Provider} from "react-redux"
import { Provider as ReduxQueryProvider } from "redux-query-react"
import {Route, Router} from "react-router"
import {act} from "react-dom/test-utils"
import {getQueries} from "../lib/queries/util"
import {ReactReduxContext} from "react-redux"
import configureMockStore from "redux-mock-store"

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
    this.wrapper = null
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
        },
      }))
  }

  cleanup() {
    this.actions = []
    this.sandbox.restore()
  }

  configureRenderer(
    WrappedComponent: Class<React.Component<*, *>>,
    InnerComponent: Class<React.Component<*, *>>,
    defaultState: Object,
    defaultProps = {}
  ) {
    const history = this.browserHistory
    return async (
      extraProps = {},
      beforeRenderActions = [],
      extraState = {},
    ) => {
      const initialState = R.mergeDeepRight(defaultState, extraState)
      const store = configureStoreMain(initialState)
      beforeRenderActions.forEach(action => store.dispatch(action))

      const ComponentWithProps = () => (
        <WrappedComponent
          {...defaultProps}
          {...extraProps}
        />
      )

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
  configureHOCRenderer(
    InnerComponent: Class<React.Component<*, *>>,
    defaultState: Object,
    defaultProps = {}
  ) {
    const history = this.browserHistory
    return async (extraState = {}, extraProps = {}) => {
      const initialState = R.mergeDeepRight(defaultState, extraState)
      const store = configureStoreMain(initialState)
      const storeContext = {
        store
      }
      const wrapper = await shallow(
        <InnerComponent
          dispatch={store.dispatch}
          history={history}
          {...defaultProps}
          {...extraProps}
        />,
        {
          wrappingComponent:      Provider,
          wrappingComponentProps: {
            store:   store,
            context: storeContext
          }
        }
      )

      // just a little convenience method
      store.getLastAction = function() {
        const actions = this.getActions()
        return actions[actions.length - 1]
      }
      const inner = wrapper
      // dive through layers of HOCs until we reach the desired inner component
      await act(async () => {
        inner.update()
      })
      await act(async () => {
        wrapper.update()
      })

      return { wrapper, inner, store }
    }
  }
}
