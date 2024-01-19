// @flow

import React from "react"

import MixedLink from "./MixedLink"
import { routes } from "../lib/urls"

type Props = {
  mobileView: boolean
}

const AnonymousMenu = ({ mobileView }: Props) => {
  const identifierPostfix = mobileView ? "Mobile" : "Desktop"
  const makeNavLink = (text: string) => {
    return mobileView ? (
      <span data-bs-target="#nav" data-bs-toggle="collapse">
        {text}
      </span>
    ) : (
      text
    )
  }
  return (
    <ul>
      <li>
        <MixedLink
          id="catalog"
          dest={routes.catalog}
          className="top-nav-link"
          aria-label="Catalog"
        >
          {makeNavLink("Catalog")}
        </MixedLink>
      </li>
      <li>
        <MixedLink
          id={"login".concat(identifierPostfix)}
          dest={routes.login.begin}
          className="simple"
          aria-label="Sign In"
        >
          {makeNavLink("Sign In")}
        </MixedLink>
      </li>
      <li>
        <MixedLink
          id={"createAccount".concat(identifierPostfix)}
          dest={routes.register.begin}
          className="simple button"
          aria-label="Create Account"
        >
          {makeNavLink("Create Account")}
        </MixedLink>
      </li>
    </ul>
  )
}

export default AnonymousMenu
