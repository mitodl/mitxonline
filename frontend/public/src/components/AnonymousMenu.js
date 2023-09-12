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
  const newDesign = checkFeatureFlag("mitxonline-new-header")
  return (
    <ul>
      <li>
        <MixedLink
          id={"login".concat(identifierPostfix)}
          dest={routes.login.begin}
          className="simple"
          aria-label="Sign In"
        >
          Sign In
        </MixedLink>
      </li>
      <li>
        <MixedLink
          id={"createAccount".concat(identifierPostfix)}
          dest={routes.register.begin}
          className="simple button"
          aria-label="Create Account"
        >
          Create {newDesign && mobileView ? "" : "Account"}
        </MixedLink>
      </li>
    </ul>
  )
}

export default AnonymousMenu
