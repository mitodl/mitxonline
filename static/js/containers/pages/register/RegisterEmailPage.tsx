import { FormikActions } from "formik"
import qs from "query-string"
import React, { useCallback } from "react"
import DocumentTitle from "react-document-title"
import { useHistory } from "react-router"
import { QueryResponse } from "redux-query"
import { useMutation } from "redux-query-react"
import RegisterEmailForm, {
  RegisterEmailFormValues
} from "../../../components/forms/RegisterEmailForm"
import { ALERT_TYPE_TEXT, REGISTER_EMAIL_PAGE_TITLE } from "../../../constants"
import {
  useNotifications,
  UserNotification
} from "../../../hooks/notifications"
import useQueryString from "../../../hooks/querystring"
import useSettings from "../../../hooks/settings"
import {
  handleAuthResponse,
  STATE_ERROR,
  STATE_LOGIN_PASSWORD,
  STATE_REGISTER_CONFIRM_SENT,
  STATE_REGISTER_EMAIL
} from "../../../lib/auth"
import queries from "../../../lib/queries"
import { routes } from "../../../lib/urls"
import { AuthResponse } from "../../../types/auth"

const accountExistsNotification = (
  email: string
): [string, UserNotification] => [
  "account-exists",
  {
    type:  ALERT_TYPE_TEXT,
    color: "danger",
    props: {
      text: `You already have an account with ${email}. Enter password to sign in.`
    }
  }
]

const accountBlockedNotification = (
  supportEmail: string
): [string, UserNotification] => [
  "account-blocked",
  {
    type:  ALERT_TYPE_TEXT,
    color: "danger",
    props: {
      text: (
        <>
          <div key="1">
            Please contact{" "}
            <a
              style={{
                color:          "white",
                textDecoration: "underline"
              }}
              href={`mailto:${supportEmail}`}
            >
              {" "}
              customer support
            </a>{" "}
            to complete your registration.
          </div>
        </>
      )
    }
  }
]

export default function RegisterEmailPage() {
  const history = useHistory()
  const { next } = useQueryString<{ next: string }>()
  /* eslint-disable-next-line camelcase */
  const { site_name, support_email } = useSettings()
  const { addNotification } = useNotifications()

  const [
    ,
    registerEmail
  ] = useMutation(
    (
      email: string,
      recaptcha: string | null | undefined,
      nextUrl: string | null | undefined
    ) => queries.auth.registerEmailMutation(email, recaptcha, nextUrl)
  )

  const onSubmit = useCallback(
    async (
      { email, recaptcha }: RegisterEmailFormValues,
      { setSubmitting, setErrors }: FormikActions<RegisterEmailFormValues>
    ) => {
      try {
        const { body } = (await registerEmail(
          email,
          recaptcha,
          next
        )) as QueryResponse<AuthResponse>
        handleAuthResponse(history, body, {
          [STATE_REGISTER_CONFIRM_SENT]: () => {
            const params = qs.stringify({
              email
            })
            history.push(`${routes.register.confirmSent}?${params}`)
          },
          [STATE_REGISTER_EMAIL]: () =>
            /* eslint-disable-next-line camelcase */
            addNotification(...accountBlockedNotification(support_email)),
          [STATE_LOGIN_PASSWORD]: () =>
            addNotification(...accountExistsNotification(email)),
          // eslint-disable-next-line camelcase
          [STATE_ERROR]: ({ field_errors }: AuthResponse) =>
            setErrors(field_errors)
        })
      } finally {
        setSubmitting(false)
      }
    },
    [addNotification, history]
  )

  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${REGISTER_EMAIL_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1>Create Account</h1>
          </div>
          <RegisterEmailForm onSubmit={onSubmit} />
        </div>
      </div>
    </DocumentTitle>
  )
}
