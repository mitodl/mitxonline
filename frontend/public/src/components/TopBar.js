// @flow
import React from "react"

import { routes } from "../lib/urls"
import UserMenu from "./UserMenu"
import AnonymousMenu from "./AnonymousMenu"
import InstituteLogo from "./InstituteLogo"
import type { Location } from "react-router"
import NotificationContainer from "./NotificationContainer"

import type { CurrentUser } from "../flow/authTypes"

import posthog from "posthog-js"

/* global SETTINGS:false */
posthog.init(SETTINGS.posthog_api_token, {
  api_host: SETTINGS.posthog_api_host
})

type Props = {
  currentUser: CurrentUser,
  location: ?Location
}

const TopBar = ({ currentUser }: Props) => (
  <header className="site-header d-flex d-flex flex-column">
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
      <div
        id="nav"
        className={ `px-0 justify-content-end`}
      >
        <div className="full-screen-menu">
          {currentUser.is_authenticated ? (
            <UserMenu currentUser={currentUser} useScreenOverlay={false} />
          ) : (
            <AnonymousMenu mobileView={false} newDesign={true}/>
          )}
        </div>
        {currentUser.is_authenticated ? (
          <div className="mobile-menu">
            <UserMenu currentUser={currentUser} useScreenOverlay={true} />
          </div>
        ) : (
          <div className="mobile-auth-buttons">
            <AnonymousMenu mobileView={true} newDesign={true}/>
          </div>
        )}
      </div>
    </nav>
  </header>
)

export default TopBar
