// @flow
/* global SETTINGS:false*/
import React from "react"
import * as Sentry from "@sentry/browser"
import posthog from "posthog-js"

import type { CurrentUser } from "../flow/authTypes"
import type { Location } from "react-router"
import TopBar from "./TopBar"

type Props = {
  currentUser: CurrentUser,
  cartItemsCount: number,
  location: ?Location
}

const Header = ({ currentUser, cartItemsCount, location }: Props) => {
  if (currentUser && currentUser.is_authenticated) {
    Sentry.getCurrentScope().setUser({
      id:       currentUser.id,
      email:    currentUser.email,
      username: currentUser.username,
      name:     currentUser.name
    })
    if (currentUser.global_id) {
      // Identify by the Keycloak global id rather than our Django user id.
      // This posthog project is shared with other MIT applications, and
      // xpro identifies people by its own integer user ids, so integer ids
      // collide across applications. Users with no global id are left
      // unidentified rather than identified by a colliding id.
      posthog.identify(currentUser.global_id, {
        environment: SETTINGS.environment,
        user_id:     currentUser.id
      })
    }
  } else {
    Sentry.getCurrentScope().setUser(null)
  }
  return (
    <React.Fragment>
      <TopBar
        currentUser={currentUser}
        cartItemsCount={cartItemsCount}
        location={location}
      />
    </React.Fragment>
  )
}

export default Header
