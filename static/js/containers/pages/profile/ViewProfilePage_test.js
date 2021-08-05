// @flow
import { assert } from "chai"

import ViewProfilePage, {
  ViewProfilePage as InnerViewProfilePage
} from "./ViewProfilePage"
import { makeAnonymousUser, makeUser } from "../../../factories/user"
import IntegrationTestHelper from "../../../util/integration_test_helper"

describe("ViewProfilePage", () => {
  let helper, renderPage
  const user = makeUser()

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    renderPage = helper.configureHOCRenderer(
      ViewProfilePage,
      InnerViewProfilePage,
      {
        entities: {
          currentUser: user
        }
      },
      {}
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders the page for a logged in user", async () => {
    const { inner } = await renderPage()
    const editBtn = inner.find("button")
    assert.isTrue(editBtn.exists())
    assert.equal(editBtn.text(), "Edit Profile")
    assert.isNull(helper.currentLocation)
    editBtn.simulate("click")
    assert.equal(helper.currentLocation.pathname, "/profile/edit/")
  })
})
