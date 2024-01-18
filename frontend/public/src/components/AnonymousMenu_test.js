// @flow
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import AnonymousMenu from "./AnonymousMenu"
import { routes } from "../lib/urls"

describe("AnonymousMenu component", () => {
  it("has a link to login", () => {
    assert.equal(
      shallow(<AnonymousMenu mobileView={false} />)
        .find("MixedLink")
        .at(1)
        .prop("dest"),
      routes.login
    )
  })

  it("has a link to register", () => {
    assert.equal(
      shallow(<AnonymousMenu mobileView={false} />)
        .find("MixedLink")
        .at(2)
        .prop("dest"),
      routes.register.begin
    )
  })

  it("has a link to create account", () => {
    assert.equal(
      shallow(<AnonymousMenu mobileView={true} />)
        .find("MixedLink")
        .at(2)
        .prop("dest"),
      routes.register.begin
    )
  })
})
