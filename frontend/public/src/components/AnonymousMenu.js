// @flow

import React from "react"

import MixedLink from "./MixedLink"
import { routes } from "../lib/urls"
import { checkFeatureFlag } from "../lib/util"

type Props = {
  mobileView: boolean
}

const AnonymousMenu = ({ mobileView }: Props) => {
  const identifierPostfix = mobileView ? "Mobile" : "Desktop"
  const newDesign = checkFeatureFlag("mitxonline-new-header", "anonymousUser")
  return (
    <ul>
      {newDesign ? (
        <li>
          <MixedLink
            id="catalog"
            dest={routes.catalog}
            className="top-nav-link"
            aria-label="Catalog"
          >
            <span data-bs-target="#nav" data-bs-toggle="collapse">
              Catalog
            </span>
          </MixedLink>
        </li>
      ) : null}
      <li>
        <MixedLink
          id={"login".concat(identifierPostfix)}
          dest={routes.login.begin}
          className="simple"
          aria-label="Sign In"
        >
          <span data-bs-target="#nav" data-bs-toggle="collapse">
            Sign In
          </span>
        </MixedLink>
      </li>
      <li>
        <MixedLink
          id={"createAccount".concat(identifierPostfix)}
          dest={routes.register.begin}
          className="simple button"
          aria-label="Create Account"
        >
          <span data-bs-target="#nav" data-bs-toggle="collapse">
            Create Account
          </span>
        </MixedLink>
      </li>
    </ul>
  )
}

export default AnonymousMenu
