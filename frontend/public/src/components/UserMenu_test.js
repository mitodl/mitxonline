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
    assert.lengthOf(userMenu.find("MixedLink"), 3)
    assert.lengthOf(userMenu.find("a"), 2)
  })

  it("links to the dashboard with a full page load", () => {
    const link = shallow(
      <UserMenu currentUser={user} useScreenOverlay={false} />
    ).find("a[aria-label='Dashboard']")
    assert.equal(link.prop("href"), routes.dashboard)
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
        .find("a[aria-label='Sign Out']")
        .prop("href"),
      routes.logout
    )
  })
})
