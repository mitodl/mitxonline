// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { ACCOUNT_SETTINGS_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync } from "redux-query"

import { addUserNotification } from "../../../actions"
import auth from "../../../lib/queries/auth"
import { routes } from "../../../lib/urls"
import { ALERT_TYPE_TEXT } from "../../../constants"

import ChangePasswordForm from "../../../components/forms/ChangePasswordForm"
import ChangeEmailForm from "../../../components/forms/ChangeEmailForm"

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
  currentUser: User
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

  render() {
    const { currentUser } = this.props

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

const mapStateToProps = createStructuredSelector({
  currentUser: currentUserSelector
})

const mapDispatchToProps = {
  changePassword,
  changeEmail,
  addUserNotification
}

export default compose(connect(mapStateToProps, mapDispatchToProps))(
  AccountSettingsPage
)
