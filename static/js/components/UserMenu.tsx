import React from "react"
import { routes } from "../lib/urls"
import { LoggedInUser } from "../types/auth"
import MixedLink from "./MixedLink"

type Props = {
  /* This is here for future use when we have custom profile avatars */
  currentUser: LoggedInUser
  useScreenOverlay: boolean
}
const desktopMenuContainerProps = {
  className: "user-menu dropdown"
}
const desktopUListProps = {
  className: "dropdown-menu dropdown-menu-right"
}
const overlayListItemProps = {
  "data-toggle": "collapse",
  "data-target": "#nav"
}
const desktopListItemProps = {
  className: "dropdown-item"
}
type MenuChildProps = {
  container?: Record<string, any>
  ul?: Record<string, any>
  li?: Record<string, any>
  dropdownIdentifier: string
}

const UserMenu = ({ currentUser, useScreenOverlay }: Props) => {
  /* eslint-disable prefer-const */
  let dropdownIdentifier = "dropdownMenuButton"
  let menuChildProps: MenuChildProps = useScreenOverlay
    ? {
      li:                 overlayListItemProps,
      dropdownIdentifier: dropdownIdentifier.concat("Mobile")
    }
    : {
      container:          desktopMenuContainerProps,
      ul:                 desktopUListProps,
      li:                 desktopListItemProps,
      dropdownIdentifier: dropdownIdentifier.concat("Desktop")
    }
  return (
    <div {...(menuChildProps.container || {})}>
      <button
        className="col-2 dropdown-toggle user-menu-button"
        id={menuChildProps.dropdownIdentifier}
        data-toggle="dropdown"
        aria-haspopup="true"
        aria-expanded="false"
      >
        {currentUser.name}
      </button>
      <ul
        {...(menuChildProps.ul || {})}
        aria-labelledby={menuChildProps.dropdownIdentifier}
      >
        <li {...(menuChildProps.li || {})}>
          <MixedLink dest={routes.profile} aria-label="Profile">
            Profile
          </MixedLink>
        </li>
        <li {...(menuChildProps.li || {})}>
          <MixedLink dest={routes.dashboard} aria-label="Dashboard">
            Dashboard
          </MixedLink>
        </li>
        <li {...(menuChildProps.li || {})}>
          <MixedLink dest={routes.accountSettings} aria-label="Account">
            Account
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
