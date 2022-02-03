import React, { useEffect } from "react"
import { useRequest } from "redux-query-react"
import Header from "../components/Header"
import { useNotifications } from "../hooks/notifications"
import { useCurrentUser } from "../hooks/user"
import {
  getStoredUserMessage,
  removeStoredUserMessage
} from "../lib/notificationsApi"
import { currentUserQuery } from "../lib/queries/users"

export default function HeaderApp() {
  const { addNotification } = useNotifications()
  const currentUser = useCurrentUser()

  useEffect(() => {
    const userMsg = getStoredUserMessage()

    if (userMsg) {
      addNotification("loaded-user-msg", {
        type:  userMsg.type,
        props: {
          text: userMsg.text
        }
      })
      removeStoredUserMessage()
    }
  }, [addNotification])

  useRequest(currentUserQuery())

  if (!currentUser) {
    // application is still loading
    return <div />
  }

  return <Header currentUser={currentUser} />
}
