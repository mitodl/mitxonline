/* global SETTINGS: false */
import { getCookie, removeCookie } from "./api"
import { isEmptyText } from "./util"
import {
  ALERT_TYPE_DANGER,
  ALERT_TYPE_SUCCESS,
  USER_MSG_COOKIE_NAME,
  USER_MSG_TYPE_COMPLETED_AUTH,
  USER_MSG_TYPE_ENROLL_BLOCKED,
  USER_MSG_TYPE_ENROLL_FAILED,
  USER_MSG_TYPE_ENROLLED
} from "../constants"

type UserMessage = {
  type: string,
  text: string
}

export function getStoredUserMessage(): UserMessage | null {
  const userMsgValue = getCookie(USER_MSG_COOKIE_NAME)
  if (!userMsgValue || isEmptyText(userMsgValue)) {
    return null
  }
  const userMsgObject = JSON.parse(decodeURIComponent(userMsgValue))
  return parseStoredUserMessage(userMsgObject)
}

export function parseStoredUserMessage(
  userMsgJson: Object
): UserMessage | null {
  const msgType = userMsgJson.type || null
  if (!msgType) {
    return null
  }
  let alertType, msgText
  switch (msgType) {
  case USER_MSG_TYPE_ENROLLED:
    alertType = ALERT_TYPE_SUCCESS
    msgText = userMsgJson.run
      ? `Success! You've been enrolled in ${userMsgJson.run}.`
      : null
    break
  case USER_MSG_TYPE_ENROLL_FAILED:
    alertType = ALERT_TYPE_DANGER
    msgText = `Something went wrong with your enrollment. Please contact support at ${
      SETTINGS.support_email
    }.`
    break
  case USER_MSG_TYPE_ENROLL_BLOCKED:
    alertType = ALERT_TYPE_DANGER
    msgText =
        "We're sorry, your country is currently blocked from enrolling in this course."
    break
  case USER_MSG_TYPE_COMPLETED_AUTH:
    alertType = ALERT_TYPE_SUCCESS
    msgText = "Account created!"
    break
  default:
    return null
  }
  if (!alertType || !msgText) {
    return null
  }
  return {
    type: alertType,
    text: msgText
  }
}

export function removeStoredUserMessage(): null {
  removeCookie(USER_MSG_COOKIE_NAME)
}

export const getNotificationAlertProps = (
  notificationType: string
): {
  color?: string
} => {
  switch (notificationType) {
  case ALERT_TYPE_SUCCESS:
    return { color: ALERT_TYPE_SUCCESS }
  case ALERT_TYPE_DANGER:
    return { color: ALERT_TYPE_DANGER }
  default:
    return {}
  }
}
