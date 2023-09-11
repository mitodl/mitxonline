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

const TopBar = ({ currentUser }: Props) => (
  <header className="site-header new-design d-flex d-flex flex-column">
    <NotificationContainer id="notifications-container" />
    <nav
      className={`order-1 sub-nav navbar navbar-expand-md top-navbar ${
        currentUser.is_authenticated ? "nowrap login" : ""
      }`}
    >
      <div className="top-branding">
        <a href="https://mit.edu" className="logo-link">
          <InstituteLogo />
        </a>
        <div className="divider-grey" />
        <a href={routes.root} className="mitx-online-link">
          MITx Online
        </a>
      </div>
      {currentUser.is_authenticated ? (
        <>
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
            <div className="full-screen-top-menu">
              <UserMenu currentUser={currentUser} useScreenOverlay={false} />
            </div>
            <div className="mobile-menu">
              <UserMenu currentUser={currentUser} useScreenOverlay={true} />
            </div>
          </div>
        </>
      ) : (
        <div className="justify-content-end">
          <div className="full-screen-top-menu">
            <AnonymousMenu mobileView={false}/>
          </div>
          <div className="mobile-auth-buttons">
            <AnonymousMenu mobileView={true}/>
          </div>
        </div>
      )}
    </nav>
  </header>
)

export default TopBar
