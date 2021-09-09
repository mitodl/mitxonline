// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import UserMenu from "./UserMenu"
import { routes } from "../lib/urls"
import { makeUser } from "../factories/user"

describe("UserMenu component", () => {
  const user = makeUser()
  it("has the correct number of menu links", () => {
    assert.isOk(
      shallow(<UserMenu currentUser={user} useScreenOverlay={false} />)
        .find("MixedLink")
        .exists()
    )
  })

  it("has the correct number of menu links in the mobile view", () => {
    assert.equal(
      shallow(<UserMenu currentUser={user} useScreenOverlay={true} />).find(
        ".authenticated-menu"
      ).length,
      4
    )
  })

  it("has a link to logout", () => {
    assert.equal(
      shallow(<UserMenu currentUser={user} useScreenOverlay={false} />)
        .find("MixedLink")
        .at(3)
        .prop("dest"),
      routes.logout
    )
  })
})
