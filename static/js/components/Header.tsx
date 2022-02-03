import * as Sentry from "@sentry/browser"
import React from "react"
import { CurrentUser } from "../types/auth"
import NotificationContainer from "./NotificationContainer"
import TopAppBar from "./TopAppBar"

type Props = {
  currentUser: CurrentUser
}

const Header = ({ currentUser }: Props) => {
  if (currentUser && currentUser.is_authenticated) {
    Sentry.configureScope(scope => {
      scope.setUser({
        id:       currentUser.id.toString(),
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

  return (
    <React.Fragment>
      <TopAppBar currentUser={currentUser} />
      <NotificationContainer />
    </React.Fragment>
  )
}

export default Header
