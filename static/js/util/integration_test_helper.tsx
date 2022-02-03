import { mount, ReactWrapper } from "enzyme"
import {
  createMemoryHistory,
  Location,
  LocationState,
  MemoryHistory
} from "history"
import React, { ComponentType, FunctionComponent } from "react"
import { act } from "react-dom/test-utils"
import { Provider } from "react-redux"
import { Router } from "react-router"
import { Action } from "redux"
import { Provider as ReduxQueryProvider } from "redux-query-react"
import sinon, { SinonSandbox, SinonStub } from "sinon"
import { getQueries } from "../lib/redux_query"
import { ReduxState } from "../reducers"
import configureStore, { Store } from "../store/configureStore"
import * as networkInterfaceFuncs from "../store/network_interface"

export interface RenderResult {
  wrapper: ReactWrapper
  store: Store
}

export default class IntegrationTestHelper {
  browserHistory: MemoryHistory
  sandbox: SinonSandbox
  actions: Array<Action>
  handleRequestStub: SinonStub
  currentLocation: Location<LocationState> | null
  scrollIntoViewStub: SinonStub
  wrapper?: ReactWrapper | null
  // just roll with it :)
  realWarn: any
  div: HTMLDivElement

  constructor() {
    this.sandbox = sinon.createSandbox({})
    this.actions = []

    this.scrollIntoViewStub = this.sandbox.stub()
    window.HTMLDivElement.prototype.scrollIntoView = this.scrollIntoViewStub
    window.HTMLFieldSetElement.prototype.scrollIntoView = this.scrollIntoViewStub
    this.browserHistory = createMemoryHistory()
    this.currentLocation = null
    this.wrapper = null
    this.div = document.createElement("div")
    document.body.appendChild(this.div)
    this.browserHistory.listen(url => {
      this.currentLocation = url
    })

    // we return "no match" here as a sentinel default response
    // basically, if this is returned it's an indication that mocks
    // weren't set up correctly for the URL and HTTP verb which
    // handleRequestStub is being called with.
    this.handleRequestStub = this.sandbox.stub().returns("no match")
    this.sandbox
      .stub(networkInterfaceFuncs, "makeRequest")
      .callsFake((url, method, options) => ({
        execute: callback => {
          let response = this.handleRequestStub(url, method, options)
          // if response is "no match" then no call to `.withArgs` has
          // been sufficient to match the current URL and method combo.
          // in that case, we'll log to `console.error` the method and
          // url and thereby fail the test.
          if (response === "no match") {
            console.error(`unmatched ${method} request made to ${url}`)
            response = {
              body:   {},
              status: 200
            }
          }
          const err = null
          const resStatus = response.status ?? 0
          const resBody = response.body ?? undefined
          const resText = response.text ?? undefined
          const resHeaders = response.header ?? undefined

          callback(err, resStatus, resBody, resText, resHeaders)
        },
        abort: () => {
          throw new Error("Aborts currently unhandled")
        }
      }))
    this.realWarn = console.warn
    // eslint-disable-next-line @typescript-eslint/no-empty-function
    console.warn = () => {}
  }

  mockRequest(
    url: string,
    method: "GET" | "POST" | "PATCH" | "DELETE",
    responseBody: unknown,
    code: number
  ): sinon.SinonStub {
    return this.handleRequestStub.withArgs(url, method).returns({
      body:   responseBody,
      status: code
    })
  }

  /**
   * Convenience method for mocking out a GET request
   *
   * pass the API url you want to mock and the object which should be
   * returned as the request body!
   */
  mockGetRequest(url: string, body: unknown, code = 200): sinon.SinonStub {
    return this.mockRequest(url, "GET", body, code)
  }

  /**
   * Convenience method for mocking out a POST request
   */
  mockPostRequest(url: string, body: unknown, code = 201): sinon.SinonStub {
    return this.mockRequest(url, "POST", body, code)
  }

  /**
   * Convenience method for mocking out a PATCH request
   */
  mockPatchRequest(url: string, body: unknown, code = 200): sinon.SinonStub {
    return this.mockRequest(url, "PATCH", body, code)
  }

  /**
   * Convenience method for mocking out a DELETE request
   */
  mockDeleteRequest(url: string, body: unknown, code = 204): sinon.SinonStub {
    return this.mockRequest(url, "DELETE", body, code)
  }

  /**
   * Clean up after yourself!
   */
  cleanup(unmount = true): void {
    this.actions = []
    this.sandbox.restore()

    if (this.wrapper && unmount) {
      this.wrapper.unmount()
      delete this.wrapper
      this.wrapper = null
    }
    console.warn = this.realWarn
    this.div.remove()
  }

  /**
   * Configure the integration test renderer!
   *
   * Takes a component, some defaultProps, and a defaultState for
   * the Redux store and returns a render function which can be used
   * to render the component and then make assertions and so on about it.
   *
   * Usage example:
   *
   * ```ts
   * const render = helper.configureRenderer(
   *   MyComponent, { prop: 'default value' }
   * )
   * const { wrapper, store } = await render()
   * ```
   */
  configureRenderer(
    Component: ComponentType<any> | FunctionComponent<any>,
    defaultProps: Record<string, any> = {},
    defaultState?: Partial<ReduxState>
  ): TestRenderer {
    return async (
      extraProps: Record<string, any> = {},
      beforeRenderActions: Array<any> = [],
      perRenderDefaultState?: Partial<ReduxState>
    ): Promise<RenderResult> => {
      const store = configureStore(defaultState ?? perRenderDefaultState)
      beforeRenderActions.forEach(action => store.dispatch(action))

      const wrapper = mount(
        <Provider store={store}>
          <ReduxQueryProvider queriesSelector={getQueries}>
            <Router history={this.browserHistory}>
              <Component {...defaultProps} {...extraProps} />
            </Router>
          </ReduxQueryProvider>
        </Provider>,
        {
          attachTo: this.div
        }
      )
      this.wrapper = wrapper
      wrapper.update()
      return { wrapper, store }
    }
  }

  /**
   * Configure the integration test renderer, additionally wrapping the render in act()
   *
   * Takes a component, some defaultProps, and a defaultState for
   * the Redux store and returns a render function which can be used
   * to render the component and then make assertions and so on about it.
   *
   * Usage example:
   *
   * ```ts
   * const render = helper.configureActRenderer(
   *   MyComponent, { prop: 'default value' }
   * )
   * const { wrapper, store } = await render()
   * ```
   */
  configureActRenderer(
    Component: ComponentType<any> | FunctionComponent<any>,
    defaultProps: Record<string, any> = {},
    defaultState?: Partial<ReduxState>
  ): TestRenderer {
    const _renderer = this.configureRenderer(
      Component,
      defaultProps,
      defaultState
    )

    return async (
      extraProps: Record<string, any> = {},
      beforeRenderActions: Array<any> = [],
      perRenderDefaultState?: Partial<ReduxState>
    ): Promise<RenderResult> => {
      let _store, _wrapper

      await act(async () => {
        const { store, wrapper } = await _renderer(
          extraProps,
          beforeRenderActions,
          perRenderDefaultState
        )

        _store = store
        _wrapper = wrapper
      })

      return {
        // @ts-ignore
        store:   _store,
        // @ts-ignore
        wrapper: _wrapper
      }
    }
  }
}

export type TestRenderer = (
  extraProps?: Record<string, any>,
  beforeRenderActions?: Array<any>,
  perRenderDefaultState?: Partial<ReduxState>
) => Promise<RenderResult>
