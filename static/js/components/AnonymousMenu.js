// @flow
/* global SETTINGS:false */
import React, { Fragment } from "react"

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
  return (
    <ul className="menu-holder">
      <li {...listItemProps || {}}>
        <MixedLink
          dest={routes.login.begin}
          className="simple"
          aria-label="Login"
        >
          Sign In
        </MixedLink>
      </li>
      <li {...listItemProps || {}}>
        <MixedLink
          dest={routes.register.begin}
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
