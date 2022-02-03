import { FormikActions } from "formik"
import React, { useCallback } from "react"
import DocumentTitle from "react-document-title"
import { useHistory } from "react-router"
import { useMutation } from "redux-query-react"
import ChangeEmailForm, {
  ChangeEmailFormValues
} from "../../../components/forms/ChangeEmailForm"
import ChangePasswordForm, {
  ChangePasswordFormValues
} from "../../../components/forms/ChangePasswordForm"
import {
  ACCOUNT_SETTINGS_PAGE_TITLE,
  ALERT_TYPE_TEXT
} from "../../../constants"
import { useNotifications } from "../../../hooks/notifications"
import useSettings from "../../../hooks/settings"
import { useLoggedInUser } from "../../../hooks/user"
import * as auth from "../../../lib/queries/auth"
import { routes } from "../../../lib/urls"

export default function AccountSettingsPage() {
  const history = useHistory()
  const { addNotification } = useNotifications()
  const user = useLoggedInUser()
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()

  const [, changeEmail] = useMutation(auth.changeEmailMutation)
  const [, changePassword] = useMutation(auth.changePasswordMutation)

  const onSubmitPasswordForm = useCallback(
    async (
      { oldPassword, newPassword }: ChangePasswordFormValues,
      { setSubmitting, resetForm }: FormikActions<ChangePasswordFormValues>
    ) => {
      try {
        const response = await changePassword(oldPassword, newPassword)
        let alertText, color

        if (response?.status === 200 || response?.status === 204) {
          alertText = "Your password has been updated successfully."
          color = "success"
        } else {
          alertText = "Unable to reset your password, please try again later."
          color = "danger"
        }

        addNotification("password-change", {
          type:  ALERT_TYPE_TEXT,
          color: color,
          props: {
            text: alertText
          }
        })
        history.push(routes.accountSettings)
      } finally {
        resetForm()
        setSubmitting(false)
      }
    },
    []
  )

  const onSubmitEmailForm = useCallback(
    async (
      { email, confirmPassword }: ChangeEmailFormValues,
      { setSubmitting, resetForm }: FormikActions<ChangeEmailFormValues>
    ) => {
      try {
        const response = await changeEmail(email, confirmPassword)
        let alertText, color

        if (response?.status === 200 || response?.status === 201) {
          alertText =
            "You have been sent a verification email on your updated address. Please click on the link in the email to finish email address update."
          color = "success"
        } else {
          alertText =
            "Unable to update your email address, please try again later."
          color = "danger"
        }

        addNotification("email-change", {
          type:  ALERT_TYPE_TEXT,
          color: color,
          props: {
            text: alertText
          }
        })
        history.push(routes.accountSettings)
      } finally {
        resetForm()
        setSubmitting(false)
      }
    },
    []
  )

  return user ? (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${ACCOUNT_SETTINGS_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page account-settings-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1>Account</h1>
          </div>
          <ChangeEmailForm user={user} onSubmit={onSubmitEmailForm} />
          <ChangePasswordForm onSubmit={onSubmitPasswordForm} />
        </div>
      </div>
    </DocumentTitle>
  ) : null
}
