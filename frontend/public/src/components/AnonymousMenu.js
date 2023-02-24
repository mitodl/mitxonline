// @flow

import React from "react"

import MixedLink from "./MixedLink"
import { routes } from "../lib/urls"

type Props = {
  useScreenOverlay: boolean
}

const overlayListItemProps = {
  "data-toggle": "collapse",
  "data-target": "#nav"
}

const AnonymousMenu = ({ useScreenOverlay }: Props) => {
  /* eslint-disable prefer-const */
  let listItemProps: Object
  listItemProps = useScreenOverlay ? overlayListItemProps : null
  let identifierPostfix = useScreenOverlay ? "Mobile" : "Desktop"
  return (
    <ul>
      <li {...(listItemProps || {})}>
        <MixedLink
          id={"login".concat(identifierPostfix)}
          dest={routes.login.begin}
          className="simple"
          aria-label="Sign In"
        >
          Sign In
        </MixedLink>
      </li>
      <li {...(listItemProps || {})}>
        <MixedLink
          id={"createAccount".concat(identifierPostfix)}
          dest={routes.login.begin}
          className="simple button"
          aria-label="Create Account"
        >
          Create Account
        </MixedLink>
      </li>
    </ul>
  )
}

export default AnonymousMenu
