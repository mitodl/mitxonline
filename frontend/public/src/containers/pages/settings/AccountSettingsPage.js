// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { ACCOUNT_SETTINGS_PAGE_TITLE } from "../../../constants"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync } from "redux-query"
import { connectRequest } from "redux-query-react"

import { addUserNotification } from "../../../actions"
import auth from "../../../lib/queries/auth"
import notificationPreferencesQueries, {
  notificationPreferencesSelector
} from "../../../lib/queries/notificationPreferences"
import { routes } from "../../../lib/urls"
import { ALERT_TYPE_TEXT } from "../../../constants"

import ChangePasswordForm from "../../../components/forms/ChangePasswordForm"
import ChangeEmailForm from "../../../components/forms/ChangeEmailForm"
import NotificationPreferences from "../../../components/NotificationPreferences"

import type { User } from "../../../flow/authTypes"

import { createStructuredSelector } from "reselect"
import { currentUserSelector } from "../../../lib/queries/users"

import type { RouterHistory } from "react-router"
import type { ChangePasswordFormValues } from "../../../components/forms/ChangePasswordForm"
import type { ChangeEmailFormValues } from "../../../components/forms/ChangeEmailForm"

type Props = {
  history: RouterHistory,
  changePassword: (
    currentPassword: string,
    newPassword: string,
    confirmPasswordChangePassword: string
  ) => Promise<any>,
  changeEmail: (newEmail: string, password: string) => Promise<any>,
  addUserNotification: Function,
  currentUser: User,
  notificationPreferences: ?Object,
  notificationPreferencesRequest: ?Object,
  updateNotificationPreference: (
    notificationApp: string,
    notificationType: string,
    notificationChannel: string,
    payload: Object
  ) => Promise<any>,
  forceRequest: () => Promise<any>
}

export class AccountSettingsPage extends React.Component<Props> {
  async onSubmitPasswordForm(
    {
      currentPassword,
      newPassword,
      confirmPasswordChangePassword
    }: ChangePasswordFormValues,
    { setSubmitting, resetForm }: any
  ) {
    const { addUserNotification, changePassword, history } = this.props

    try {
      const response = await changePassword(
        currentPassword,
        newPassword,
        confirmPasswordChangePassword
      )

      let alertText, color
      if (response.status === 200 || response.status === 204) {
        alertText = "Your password has been updated successfully."
        color = "success"
      } else {
        alertText = "Unable to update your password, please try again later."
        color = "danger"
      }

      addUserNotification({
        "password-change": {
          type:  ALERT_TYPE_TEXT,
          color: color,
          props: {
            text: alertText
          }
        }
      })

      history.push(routes.accountSettings)
    } finally {
      resetForm()
      setSubmitting(false)
    }
  }

  async onSubmitEmailForm(
    { email, confirmPasswordEmailChange }: ChangeEmailFormValues,
    { setSubmitting, resetForm }: any
  ) {
    const { addUserNotification, changeEmail, history } = this.props

    try {
      const response = await changeEmail(email, confirmPasswordEmailChange)

      let alertText, color
      if (response.status === 200 || response.status === 201) {
        alertText =
          "You have been sent a verification email on your updated address. Please click on the link in the email to finish email address update."
        color = "success"
      } else {
        alertText =
          "Unable to update your email address, please try again later."
        color = "danger"
      }

      addUserNotification({
        "email-change": {
          type:  ALERT_TYPE_TEXT,
          color: color,
          props: {
            text: alertText
          }
        }
      })

      history.push(routes.accountSettings)
    } finally {
      resetForm()
      setSubmitting(false)
    }
  }

  async onChangeNotificationPreference(
    notificationApp: string,
    notificationType: string,
    notificationChannel: string,
    payload: Object
  ) {
    const { updateNotificationPreference, addUserNotification, forceRequest } =
      this.props

    const response = await updateNotificationPreference(
      notificationApp,
      notificationType,
      notificationChannel,
      payload
    )

    if (response.status !== 200) {
      addUserNotification({
        "notification-preference-change": {
          type:  ALERT_TYPE_TEXT,
          color: "danger",
          props: {
            text:
              response.status === 429 ?
                "Too many changes at once. Please wait a moment and try again." :
                "We could not save that notification setting. Please try again."
          }
        }
      })
      // Deliberately no re-read here. Nothing changed upstream, and on a 429
      // an immediate GET would spend the throttle we were just asked to back
      // off from. Dispatching the alert re-renders the page, which resyncs the
      // controlled inputs from props.
      return
    }

    // Re-read rather than patching local state: the LMS fans a grouped change
    // out to several types, so the response is not enough to render from.
    await forceRequest()
  }

  /**
   * Why the notification controls cannot be shown, or null to show them.
   *
   * The section itself always renders so that /account-settings/#notifications
   * -- the target the Open edX notifications gear links to -- resolves even
   * when we have no preferences to display.
   */
  notificationsNotice() {
    const { notificationPreferences, notificationPreferencesRequest } =
      this.props
    const request = notificationPreferencesRequest || {}

    if (notificationPreferences) {
      // The LMS gates the whole feature with show_preferences.
      return notificationPreferences.show_preferences === false ?
        "Notifications are not enabled for your courses." :
        null
    }

    if (!request.isFinished) {
      return "Loading your notification settings..."
    }

    if (request.status === 409) {
      return "Your course account is still being set up. Please check back shortly."
    }

    return "We could not load your notification settings. Please try again later."
  }

  render() {
    const { currentUser, notificationPreferences } = this.props

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${ACCOUNT_SETTINGS_PAGE_TITLE}`}
      >
        <>
          {currentUser ? (
            <div role="banner" className="std-page-header">
              <h1>{ACCOUNT_SETTINGS_PAGE_TITLE}</h1>
            </div>
          ) : null}

          <div className="std-page-body container auth-page">
            <div className="std-card std-card-auth">
              <div className="std-card-body my-account-page">
                {SETTINGS.api_gateway_enabled ? (
                  <section className="email-section">
                    <h2>Email</h2>

                    <div className="row">{currentUser.email}</div>
                    <a
                      aria-label="change email"
                      className="btn btn-primary btn-gradient-red-to-blue"
                      href={routes.account.action.updateEmail}
                    >
                      Change Email
                    </a>
                  </section>
                ) : (
                  <ChangeEmailForm
                    user={currentUser}
                    onSubmit={this.onSubmitEmailForm.bind(this)}
                  />
                )}
                <hr />
                {SETTINGS.api_gateway_enabled ? (
                  <section className="password-section">
                    <h2>Password</h2>
                    <a
                      aria-label="change password"
                      className="btn btn-primary btn-gradient-red-to-blue"
                      href={routes.account.action.updatePassword}
                    >
                      Change Password
                    </a>
                  </section>
                ) : (
                  <ChangePasswordForm
                    onSubmit={this.onSubmitPasswordForm.bind(this)}
                  />
                )}
              </div>
            </div>

            <div className="std-card std-card-auth">
              <div className="std-card-body my-account-page">
                <NotificationPreferences
                  preferences={
                    notificationPreferences ?
                      notificationPreferences.data :
                      null
                  }
                  showEmailPreferences={
                    !notificationPreferences ||
                    notificationPreferences.show_email_preferences !== false
                  }
                  notice={this.notificationsNotice()}
                  onChange={this.onChangeNotificationPreference.bind(this)}
                />
              </div>
            </div>
          </div>
        </>
      </DocumentTitle>
    )
  }
}

const changePassword = (oldPassword: string, newPassword: string) =>
  mutateAsync(auth.changePasswordMutation(oldPassword, newPassword))

const changeEmail = (newEmail: string, password: string) =>
  mutateAsync(auth.changeEmailMutation(newEmail, password))

const notificationPreferencesRequestSelector = pathOr(null, [
  "queries",
  "notificationPreferences"
])

const mapStateToProps = createStructuredSelector({
  currentUser:                    currentUserSelector,
  notificationPreferences:        notificationPreferencesSelector,
  notificationPreferencesRequest: notificationPreferencesRequestSelector
})

const updateNotificationPreference = (
  notificationApp: string,
  notificationType: string,
  notificationChannel: string,
  payload: Object
) =>
  mutateAsync(
    notificationPreferencesQueries.updateNotificationPreferenceMutation(
      notificationApp,
      notificationType,
      notificationChannel,
      payload
    )
  )

const mapPropsToConfig = () => [
  notificationPreferencesQueries.notificationPreferencesQuery()
]

const mapDispatchToProps = {
  changePassword,
  changeEmail,
  updateNotificationPreference,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(AccountSettingsPage)
