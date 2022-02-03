import { FormikActions } from "formik"
import React, { useCallback } from "react"
import DocumentTitle from "react-document-title"
import { useHistory, useRouteMatch } from "react-router"
import { useMutation } from "redux-query-react"
import ResetPasswordForm, {
  ResetPasswordFormValues
} from "../../../components/forms/ResetPasswordForm"
import {
  ALERT_TYPE_TEXT,
  FORGOT_PASSWORD_CONFIRM_PAGE_TITLE
} from "../../../constants"
import { useNotifications } from "../../../hooks/notifications"
import useSettings from "../../../hooks/settings"
import * as auth from "../../../lib/queries/auth"
import { routes } from "../../../lib/urls"

type RouteParams = {
  token: string
  uid: string
}

export default function LoginForgotPasswordConfirmPage() {
  const { params } = useRouteMatch<RouteParams>()
  const history = useHistory()
  const { addNotification } = useNotifications()
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()

  const [, forgotPasswordConfirm] = useMutation(
    auth.forgotPasswordConfirmMutation
  )

  const onSubmit = useCallback(
    async (
      { newPassword, confirmPassword }: ResetPasswordFormValues,
      { setSubmitting }: FormikActions<ResetPasswordFormValues>
    ) => {
      const { token, uid } = params

      try {
        const response = await forgotPasswordConfirm(
          newPassword,
          confirmPassword,
          token,
          uid
        )
        let alertText, redirectRoute

        if (response?.status === 200 || response?.status === 204) {
          alertText =
            "Your password has been updated, you may use it to sign in now."
          redirectRoute = routes.login.begin
        } else {
          alertText =
            "Unable to reset your password with that link, please try again."
          redirectRoute = routes.login.forgot.begin
        }

        addNotification("forgot-password-confirm", {
          type:  ALERT_TYPE_TEXT,
          props: {
            text: alertText
          }
        })
        history.push(redirectRoute)
      } finally {
        setSubmitting(false)
      }
    },
    [addNotification, history]
  )

  return (
    <DocumentTitle
      /* eslint-disable-next-line camelcase */
      title={`${site_name} | ${FORGOT_PASSWORD_CONFIRM_PAGE_TITLE}`}
    >
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1>Password Reset!</h1>
            <p>Enter a new password for your account.</p>
          </div>
          <ResetPasswordForm onSubmit={onSubmit} />
        </div>
      </div>
    </DocumentTitle>
  )
}
