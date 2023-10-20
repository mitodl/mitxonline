// @flow
import React from "react"

import MixedLink from "./MixedLink"
import { routes } from "../lib/urls"

import type { User } from "../flow/authTypes"
import { checkFeatureFlag } from "../lib/util"

type Props = {
  /* This is here for future use when we have custom profile avatars */
  currentUser: User,
  useScreenOverlay: boolean
}

const desktopMenuContainerProps = {
  className: "user-menu dropdown"
}
const newDesktopMenuContainerProps = {
  className: "top-user-menu dropdown"
}

const desktopUListProps = {
  className: "dropdown-menu dropdown-menu-end"
}

const overlayListItemProps = {
  className: "mobile-dropdown-item"
}

const desktopListItemProps = {
  className: "dropdown-item"
}

type MenuChildProps = {
  container?: Object,
  ul?: Object,
  li?: Object
}

const UserMenu = ({ currentUser, useScreenOverlay }: Props) => {
  /* eslint-disable prefer-const */
  let menuChildProps: MenuChildProps
  let dropdownIdentifier = "dropdownMenuButton"
  const showNewDesign = checkFeatureFlag("mitxonline-new-header")
  menuChildProps = useScreenOverlay
    ? {
      li:                 overlayListItemProps,
      dropdownIdentifier: dropdownIdentifier.concat("Mobile")
    }
    : {
      container: showNewDesign
        ? newDesktopMenuContainerProps
        : desktopMenuContainerProps,
      ul:                 desktopUListProps,
      li:                 desktopListItemProps,
      dropdownIdentifier: dropdownIdentifier.concat("Desktop")
    }
  return (
    <div {...(menuChildProps.container || {})}>
      <button
        className="dropdown-toggle user-menu-button"
        id={menuChildProps.dropdownIdentifier}
        data-bs-toggle="dropdown"
        aria-haspopup="true"
        aria-expanded="false"
        type="button"
        role="menu"
      >
        {currentUser.name}
      </button>
      <ul
        {...(menuChildProps.ul || {})}
        aria-labelledby={menuChildProps.dropdownIdentifier}
      >
        <li {...(menuChildProps.li || {})}>
          <MixedLink dest={routes.profile} aria-label="Profile">
            <span data-bs-target="#nav" data-bs-toggle="collapse">Profile</span>
          </MixedLink>
        </li>
        <li {...(menuChildProps.li || {})}>
          <MixedLink dest={routes.dashboard} aria-label="Dashboard">
            <span data-bs-target="#nav" data-bs-toggle="collapse">Dashboard</span>
          </MixedLink>
        </li>
        <li {...(menuChildProps.li || {})}>
          <MixedLink dest={routes.accountSettings} aria-label="Account">
            <span data-bs-target="#nav" data-bs-toggle="collapse">Account</span>
          </MixedLink>
        </li>
        <li {...(menuChildProps.li || {})}>
          <MixedLink dest={routes.orderHistory} aria-label="Order History">
            <span data-bs-target="#nav" data-bs-toggle="collapse">Order History</span>
          </MixedLink>
        </li>
        <li {...(menuChildProps.li || {})}>
          <a href={routes.logout} aria-label="Sign Out">
            Sign Out
          </a>
        </li>
      </ul>
    </div>
  )
}

export default UserMenu
