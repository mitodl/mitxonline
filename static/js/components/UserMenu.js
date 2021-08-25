// @flow
/* global SETTINGS:false */
import React from "react"

import MixedLink from "./MixedLink"
import { routes } from "../lib/urls"

import type { User } from "../flow/authTypes"

type Props = {
  /* This is here for future use when we have custom profile avatars */
  currentUser: User
}

const UserMenu = ({ currentUser }: Props) => {
  return (
    <div className="user-menu dropdown">
      <div
        className="col-2 dropdown-toggle"
        id="dropdownMenuButton"
        data-toggle="dropdown"
        aria-haspopup="true"
        aria-expanded="false"
      >
        {currentUser.name}
      </div>
      <div className="dropdown-menu" aria-labelledby="dropdownMenuButton">
        <MixedLink
          className="dropdown-item"
          dest={routes.profile.view}
          aria-label="Profile"
        >
          Profile
        </MixedLink>
        <MixedLink
          className="dropdown-item"
          dest={routes.dashboard}
          aria-label="Dashboard"
        >
          Dashboard
        </MixedLink>
        <MixedLink
          className="dropdown-item"
          dest={routes.accountSettings}
          aria-label="Account"
        >
          Account
        </MixedLink>

        <a className="dropdown-item" href={routes.logout} aria-label="Sign Out">
          Sign Out
        </a>
      </div>
    </div>
  )
}

export default UserMenu
