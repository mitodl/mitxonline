import { partial } from "ramda"
import React from "react"
import { Alert } from "reactstrap"
import { useNotifications } from "../hooks/notifications"
import { getNotificationAlertProps } from "../lib/notificationsApi"
import { firstNotNil } from "../lib/util"
import { notificationTypeMap, TextNotification } from "./notifications"

export default function NotificationContainer() {
  const { notifications, dismissNotification } = useNotifications()

  return (
    <div className="notifications">
      {Object.keys(notifications).map(key => {
        const dismiss = partial(dismissNotification, [key])
        const notification = notifications[key]
        const alertProps = getNotificationAlertProps(notification.type)
        const color = firstNotNil([
          notification.color,
          alertProps.color,
          "info"
        ])
        const AlertBodyComponent =
          notificationTypeMap[notification.type] || TextNotification
        return (
          <Alert
            key={key}
            color={color}
            className="rounded-0 border-0"
            isOpen={!notification.dismissed}
            toggle={dismiss}
            fade={true}
          >
            <AlertBodyComponent dismiss={dismiss} {...notification.props} />
          </Alert>
        )
      })}
    </div>
  )
}
