import { dissoc } from "ramda"
import React, { createContext, useCallback, useContext, useState } from "react"
import { timeoutPromise } from "../lib/util"

export type TextNotificationProps = {
  text: React.ReactElement | string
}

export type UserNotification = {
  type: string
  color?: string
  props: TextNotificationProps
  dismissed?: boolean
}

export type UserNotifications = {
  [key: string]: UserNotification
}

export const REMOVE_DELAY_MS = 1000

export type Notifications = {
  notifications: UserNotifications
  addNotification: (key: string, notification: UserNotification) => void
  dismissNotification: (key: string) => void
}

export const NotificationsContext = createContext<Notifications>({
  // inoperable default values
  notifications:       {},
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  addNotification:     () => {},
  // eslint-disable-next-line @typescript-eslint/no-empty-function
  dismissNotification: () => {}
})

export const NotificationsProvider = ({
  children
}: {
  children: React.ReactElement
}) => {
  const [notifications, setNotifications] = useState<UserNotifications>({})

  const dismissNotification = useCallback(
    (key: string) => {
      // This sets the given message in the local state to be considered hidden, then
      // removes the message from the global state and the local hidden state after a delay.
      // The message could be simply removed from the global state to get rid of it, but the
      // local state and the delay gives the Alert a chance to animate the message out.
      setNotifications({
        ...notifications,
        [key]: {
          ...notifications[key],
          dismissed: true
        }
      })
      return timeoutPromise(() => {
        setNotifications(dissoc(key, notifications))
      }, REMOVE_DELAY_MS)
    },
    [setNotifications, notifications]
  )

  const addNotification = useCallback(
    (key: string, notification: UserNotification) => {
      setNotifications({
        ...notifications,
        [key]: {
          ...notification,
          dismissed: false
        }
      })
    },
    [setNotifications, notifications]
  )

  return (
    <NotificationsContext.Provider
      value={{ notifications, dismissNotification, addNotification }}
    >
      {children}
    </NotificationsContext.Provider>
  )
}

export const useNotifications = () => useContext(NotificationsContext)
