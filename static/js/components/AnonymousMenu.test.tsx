import { assert } from "chai"
import { shallow } from "enzyme"
import React from "react"
import { routes } from "../lib/urls"
import AnonymousMenu from "./AnonymousMenu"

describe("AnonymousMenu component", () => {
  it("has a link to login", () => {
    assert.equal(
      shallow(<AnonymousMenu useScreenOverlay={false} />)
        .find("MixedLink")
        .at(0)
        .prop("dest"),
      routes.login
    )
  })
  it("has a link to register", () => {
    assert.equal(
      shallow(<AnonymousMenu useScreenOverlay={false} />)
        .find("MixedLink")
        .at(1)
        .prop("dest"),
      routes.register.begin
    )
  })
  it("has a link to create account", () => {
    assert.equal(
      shallow(<AnonymousMenu useScreenOverlay={true} />)
        .find("MixedLink")
        .at(1)
        .prop("dest"),
      routes.register.begin
    )
  })
})
