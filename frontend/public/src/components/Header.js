// @flow
/* global SETTINGS:false*/
import React from "react"
import * as Sentry from "@sentry/browser"
import posthog from "posthog-js"

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
  let featureFlagUserId = "anonymousUser"
  if (currentUser && currentUser.is_authenticated) {
    featureFlagUserId = currentUser.id
    Sentry.configureScope(scope => {
      scope.setUser({
        id:       currentUser.id,
        email:    currentUser.email,
        username: currentUser.username,
        name:     currentUser.name
      })
    })
    posthog.identify(
      currentUser.id, {
        environment: SETTINGS.environment,
        user_id:     currentUser.id
      }
    )
  } else {
    Sentry.configureScope(scope => {
      scope.setUser(null)
    })
  }
  const showNewDesign = checkFeatureFlag(
    "mitxonline-new-header",
    featureFlagUserId
  )
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
