import { assert } from "chai"
import React from "react"
import { makeAnonymousUser, makeUser } from "../factories/user"
import { isIf } from "../lib/test_utils"
import { routes } from "../lib/urls"
import { CurrentUser } from "../types/auth"
import IntegrationTestHelper, {
  TestRenderer
} from "../util/integration_test_helper"
import PrivateRoute from "./PrivateRoute"

describe("PrivateRoute component", () => {
  let helper: IntegrationTestHelper, renderComponent: TestRenderer

  const DummyComponent = () => <div>Dummy Component</div>
  const RoutedDummyComponent = () => (
    <PrivateRoute component={DummyComponent} path={protectedPath} />
  )

  const protectedPath = "/protected/route"
  const anonUser = makeAnonymousUser()
  const loggedInUser = makeUser()

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    renderComponent = helper.configureRenderer(RoutedDummyComponent)
  })

  afterEach(() => {
    helper.cleanup()
  })
  ;([
    [false, loggedInUser, "load the route"],
    [true, anonUser, "redirect to the login page with a 'next' param"]
  ] as [boolean, CurrentUser, string][]).forEach(
    ([isAnonymous, user, desc]) => {
      it(`should ${desc} if user ${isIf(isAnonymous)} anonymous`, async () => {
        helper.browserHistory.push(protectedPath)

        const { wrapper } = await renderComponent({}, [], {
          entities: {
            currentUser: user
          }
        })
        const routeComponent = wrapper.find("Route")

        assert.isTrue(routeComponent.exists())

        if (isAnonymous) {
          expect(helper.browserHistory.location).toMatchObject({
            pathname: routes.login.begin,
            search:   `?next=${encodeURIComponent(protectedPath)}`
          })
        } else {
          expect(wrapper.exists(DummyComponent)).toBeTruthy()
        }
      })
    }
  )
})
