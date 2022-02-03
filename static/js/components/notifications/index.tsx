import React from "react"
import { ALERT_TYPE_TEXT } from "../../constants"

type TextNotificationProps = {
  dismiss: (...args: Array<any>) => any
  text: string
}

export const TextNotification = (props: TextNotificationProps) => (
  <span>{props.text}</span>
)

export const notificationTypeMap = {
  [ALERT_TYPE_TEXT]: TextNotification
}
