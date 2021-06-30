// @flow
import React from "react"

import MixedLink from "../MixedLink"
import { routes } from "../../lib/urls"
import { ALERT_TYPE_TEXT } from "../../constants"

import type { TextNotificationProps } from "../../reducers/notifications"

type ComponentProps = {
  dismiss: Function
}

export const TextNotification = (
  props: TextNotificationProps & ComponentProps
) => <span>{props.text}</span>

export const notificationTypeMap = {
  [ALERT_TYPE_TEXT]: TextNotification
}
