// @flow
/* global SETTINGS: false */
import React from "react"

import { routes } from "../lib/urls"
import MixedLink from "./MixedLink"
import UserMenu from "./UserMenu"
import type { Location } from "react-router"

import type { CurrentUser } from "../flow/authTypes"

type Props = {
  currentUser: CurrentUser,
  location: ?Location
}

const TopAppBar = ({ currentUser, location }: Props) => (
  <header className="header-holder">
    <div className="container-fluid">
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
              alt={SETTINGS.site_name}
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
        <ul
          id="nav"
          className={`${
            currentUser.is_authenticated ? "" : "collapse"
          } navbar-collapse px-0 justify-content-end`}
        >
          {currentUser.is_authenticated ? (
            <React.Fragment>
              <li>
                <UserMenu currentUser={currentUser} />
              </li>
              {/* These menu lists will show/hide based on desktop/mobile screen. */}
              <li className="authenticated-menu" data-toggle="collapse" data-target="#nav">
                <MixedLink dest={routes.profile.view} aria-label="Profile">
                  Profile
                </MixedLink>
              </li>
              <li className="authenticated-menu" data-toggle="collapse" data-target="#nav">
                <MixedLink dest={routes.accountSettings} aria-label="Settings">
                  Settings
                </MixedLink>
              </li>
              <li className="authenticated-menu" data-toggle="collapse" data-target="#nav">
                <MixedLink dest={routes.logout} aria-label="Sign Out">
                  Sign Out
                </MixedLink>
              </li>
            </React.Fragment>
          ) : (
            <React.Fragment>
              <li data-toggle="collapse" data-target="#nav">
                <MixedLink dest={routes.login.begin} aria-label="Login">
                  Sign In
                </MixedLink>
              </li>
              <li data-toggle="collapse" data-target="#nav">
                <MixedLink
                  dest={routes.register.begin}
                  className="button"
                  aria-label="Login"
                >
                  Create Account
                </MixedLink>
              </li>
            </React.Fragment>
          )}
        </ul>
      </nav>
    </div>
  </header>
)

export default TopAppBar
