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
    posthog.identify(currentUser.id, {
      environment: SETTINGS.environment,
      user_id:     currentUser.id
    })
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
