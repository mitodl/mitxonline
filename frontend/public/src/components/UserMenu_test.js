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
    const userMenu = shallow(
      <UserMenu currentUser={user} useScreenOverlay={false} />
    )
    assert.lengthOf(userMenu.find("MixedLink"), 4)
    assert.lengthOf(userMenu.find("a"), 1)
  })

  it("has the correct class applied to menu items in the mobile view", () => {
    assert.lengthOf(
      shallow(<UserMenu currentUser={user} useScreenOverlay={true} />).find(
        "ul li"
      ),
      6
    )
  })

  it("has a link to logout", () => {
    assert.equal(
      shallow(<UserMenu currentUser={user} useScreenOverlay={false} />)
        .find("a")
        .at(0)
        .prop("href"),
      routes.logout
    )
  })
})
