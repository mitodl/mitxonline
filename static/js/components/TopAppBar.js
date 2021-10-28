// @flow
/* global SETTINGS: false */
import React from "react"

import { routes } from "../lib/urls"
import UserMenu from "./UserMenu"
import AnonymousMenu from "./AnonymousMenu"
import type { Location } from "react-router"

import type { CurrentUser } from "../flow/authTypes"

type Props = {
  currentUser: CurrentUser,
  location: ?Location
}

const TopAppBar = ({ currentUser, location }: Props) => (
  <header className="site-header py-2 px-3 py-sm-3 px-sm-4">
    <nav
      className={`sub-nav navbar navbar-expand-md link-section ${
        currentUser.is_authenticated ? "nowrap login" : ""
      }`}
    >
      <div className="navbar-brand">
        <a href="https://mit.edu">
          <img
            src="/static/images/mit-logo.jpg"
            className="site-logo"
            alt="MIT Home page"
          />
        </a>
        <div className="divider-large" />
        <a href={routes.root} className="mitx-online-link">
          MITx Online
        </a>
      </div>
      <button
        className="navbar-toggler nav-opener collapsed"
        type="button"
        data-toggle="collapse"
        data-target="#nav"
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
            <AnonymousMenu useScreenOverlay={false} />
          )}
        </div>
        <div className="mobile-menu">
          {currentUser.is_authenticated ? (
            <UserMenu currentUser={currentUser} useScreenOverlay={true} />
          ) : (
            <AnonymousMenu useScreenOverlay={true} />
          )}
        </div>
      </div>
    </nav>
  </header>
)

export default TopAppBar
