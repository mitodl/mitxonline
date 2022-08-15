/* global SETTINGS: false */
import { getCookie, removeCookie } from "./api"
import { isEmptyText } from "./util"
import {
  ALERT_TYPE_DANGER,
  ALERT_TYPE_SUCCESS,
  USER_MSG_COOKIE_NAME,
  USER_MSG_TYPE_COMPLETED_AUTH,
  USER_MSG_TYPE_ENROLL_BLOCKED,
  USER_MSG_TYPE_ENROLL_DUPLICATED,
  USER_MSG_TYPE_ENROLL_FAILED,
  USER_MSG_TYPE_ENROLLED,
  USER_MSG_TYPE_PAYMENT_DECLINED,
  USER_MSG_TYPE_PAYMENT_CANCELLED,
  USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN,
  USER_MSG_TYPE_PAYMENT_ACCEPTED,
  USER_MSG_TYPE_PAYMENT_ACCEPTED_NO_VALUE,
  USER_MSG_TYPE_PAYMENT_REVIEW,
  USER_MSG_TYPE_COURSE_NON_UPGRADABLE
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
    msgText = `Something went wrong with your enrollment. Please contact support at ${SETTINGS.support_email}.`
    break
  case USER_MSG_TYPE_ENROLL_BLOCKED:
    alertType = ALERT_TYPE_DANGER
    msgText =
        "We're sorry, your country is currently blocked from enrolling in this course."
    break
  case USER_MSG_TYPE_COURSE_NON_UPGRADABLE:
    alertType = ALERT_TYPE_DANGER
    msgText =
        "The upgrade deadline for a course in your cart has passed. Please try later."
    break
  case USER_MSG_TYPE_ENROLL_DUPLICATED:
    alertType = ALERT_TYPE_DANGER
    msgText = `You have already enrolled and paid for this course. If this is unexpected, please contact customer support at ${SETTINGS.support_email}.`
    break
  case USER_MSG_TYPE_COMPLETED_AUTH:
    alertType = ALERT_TYPE_SUCCESS
    msgText = "Account created!"
    break
  case USER_MSG_TYPE_PAYMENT_DECLINED:
    alertType = ALERT_TYPE_DANGER
    msgText = "Payment was declined, please try again."
    break
  case USER_MSG_TYPE_PAYMENT_ERROR_UNKNOWN:
    alertType = ALERT_TYPE_DANGER
    msgText = "Unknown error trying to complete order."
    break
  case USER_MSG_TYPE_PAYMENT_CANCELLED:
    alertType = ALERT_TYPE_DANGER
    msgText = "Payment was cancelled."
    break
  case USER_MSG_TYPE_PAYMENT_REVIEW:
    // Probably won't hit this in production, but here to cover all possible cases
    alertType = ALERT_TYPE_SUCCESS
    msgText = "Payment is pending review."
    break
  case USER_MSG_TYPE_PAYMENT_ACCEPTED:
    alertType = ALERT_TYPE_SUCCESS
    msgText = userMsgJson.run
      ? `Success! You are now enrolled for the paid version of ${userMsgJson.run}.`
      : null
    break
  case USER_MSG_TYPE_PAYMENT_ACCEPTED_NO_VALUE:
    alertType = ALERT_TYPE_SUCCESS
    msgText = userMsgJson.run
      ? `Success! You are now enrolled for the certificate version of ${userMsgJson.run}.`
      : null
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
