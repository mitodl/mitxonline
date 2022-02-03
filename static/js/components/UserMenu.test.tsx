import { assert } from "chai"
import { shallow } from "enzyme"
import React from "react"
import { makeUser } from "../factories/user"
import { routes } from "../lib/urls"
import UserMenu from "./UserMenu"

describe("UserMenu component", () => {
  const user = makeUser()
  it("has the correct number of menu links", () => {
    const userMenu = shallow(
      <UserMenu currentUser={user} useScreenOverlay={false} />
    )
    assert.lengthOf(userMenu.find("MixedLink"), 3)
    assert.lengthOf(userMenu.find("a"), 1)
  })
  it("has the correct class applied to menu items in the mobile view", () => {
    assert.lengthOf(
      shallow(<UserMenu currentUser={user} useScreenOverlay={true} />).find(
        "ul li"
      ),
      4
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
