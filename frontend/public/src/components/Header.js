// @flow
import React from "react"
import * as Sentry from "@sentry/browser"

import TopAppBar from "./TopAppBar"

import type { CurrentUser } from "../flow/authTypes"
import type { Location } from "react-router"
import { checkFeatureFlag } from "../lib/util"
import TopBar from "./TopBar"

type Props = {
  currentUser: CurrentUser,
  location: ?Location
}

const Header = ({ currentUser, location }: Props) => {
  if (currentUser && currentUser.is_authenticated) {
    Sentry.configureScope(scope => {
      scope.setUser({
        id:       currentUser.id,
        email:    currentUser.email,
        username: currentUser.username,
        name:     currentUser.name
      })
    })
  } else {
    Sentry.configureScope(scope => {
      scope.setUser(null)
    })
  }
  const showNewDesign = checkFeatureFlag("mitxonline-new-header", currentUser ? currentUser.id : "anon")
  if (showNewDesign) {
    return (
      <React.Fragment>
        <TopBar currentUser={currentUser} location={location} />
      </React.Fragment>
    )
  } else {
    return (
      <React.Fragment>
        <TopAppBar currentUser={currentUser} location={location} />
      </React.Fragment>
    )
  }
}

export default Header
