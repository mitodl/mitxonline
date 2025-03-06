// @flow
/* global SETTINGS: false */
import React from "react"
import { assert } from "chai"
import { shallow } from "enzyme"

import AnonymousMenu from "./AnonymousMenu"
import { routes } from "../lib/urls"

describe("AnonymousMenu component (email login version)", () => {
  beforeEach(() => {
    SETTINGS.oidc_login_url = ""
  })

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

describe("AnonymousMenu component (OIDC version)", () => {
  // If we've got OIDC login enabled, these should *all* point to the URL that
  // redirects to the OIDC login flow.

  beforeEach(() => {
    SETTINGS.oidc_login_url = "https://oidc.example.com"
  })

  it("has a link to login", () => {
    assert.equal(
      shallow(<AnonymousMenu mobileView={false} />)
        .find("MixedLink")
        .at(1)
        .prop("dest"),
      SETTINGS.oidc_login_url
    )
  })

  it("has a link to login that doesn't go to the email login page", () => {
    assert.notEqual(
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
      SETTINGS.oidc_login_url
    )
  })

  it("has a link to create account", () => {
    assert.equal(
      shallow(<AnonymousMenu mobileView={true} />)
        .find("MixedLink")
        .at(2)
        .prop("dest"),
      SETTINGS.oidc_login_url
    )
  })
})
