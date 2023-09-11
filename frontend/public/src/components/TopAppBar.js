// @flow
import React from "react"

import { routes } from "../lib/urls"
import UserMenu from "./UserMenu"
import AnonymousMenu from "./AnonymousMenu"
import InstituteLogo from "./InstituteLogo"
import type { Location } from "react-router"
import NotificationContainer from "./NotificationContainer"

import type { CurrentUser } from "../flow/authTypes"

type Props = {
  currentUser: CurrentUser,
  location: ?Location
}

const TopAppBar = ({ currentUser }: Props) => (
  <header className="site-header d-flex d-flex flex-column">
    <NotificationContainer id="notifications-container" />
    <nav
      className={`order-1 sub-nav navbar navbar-expand-md link-section py-2 px-3 py-md-3 px-md-4 ${
        currentUser.is_authenticated ? "nowrap login" : ""
      }`}
    >
      <div className="navbar-brand">
        <a href="https://mit.edu" className="logo-link">
          <InstituteLogo />
        </a>
        <div className="divider-large" />
        <a href={routes.root} className="mitx-online-link">
          MITx Online
        </a>
      </div>
      <button
        className="navbar-toggler nav-opener collapsed"
        type="button"
        data-bs-toggle="collapse"
        data-bs-target="#nav"
        aria-controls="nav"
        aria-expanded="false"
        aria-label="Toggle navigation"
      >
        <span className="bar" />
        <span className="bar" />
        <span className="bar" />
      </button>
      <div
        id="nav"
        className={`${
          currentUser.is_authenticated ? "" : "collapse"
        } user-menu-overlay px-0 justify-content-end`}
      >
        <div className="full-screen-menu">
          {currentUser.is_authenticated ? (
            <UserMenu currentUser={currentUser} useScreenOverlay={false} />
          ) : (
            <AnonymousMenu mobileView={false} />
          )}
        </div>
        <div className="mobile-menu">
          {currentUser.is_authenticated ? (
            <UserMenu currentUser={currentUser} useScreenOverlay={true} />
          ) : (
            <AnonymousMenu mobileView={true} />
          )}
        </div>
      </div>
    </nav>
  </header>
)

export default TopAppBar
