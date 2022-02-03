import { FormikActions } from "formik"
import React, { useCallback, useState } from "react"
import DocumentTitle from "react-document-title"
import { Link } from "react-router-dom"
import { useMutation } from "redux-query-react"
import EmailForm from "../../../components/forms/EmailForm"
import { FORGOT_PASSWORD_PAGE_TITLE } from "../../../constants"
import useSettings from "../../../hooks/settings"
import * as auth from "../../../lib/queries/auth"
import { routes } from "../../../lib/urls"
import { isSuccessResponse } from "../../../lib/util"
import { EmailFormValues } from "../../../types/auth"

type PasswordResetTextProps = { email: string }

const PasswordResetText = ({ email }: PasswordResetTextProps) => (
  <p>
    If an account with the email <b>{email}</b> exists, an email has been sent
    with a password reset link.
  </p>
)

type CustomerSupportProps = { isError: boolean }

const CustomerSupport = ({ isError }: CustomerSupportProps) => {
  /* eslint-disable-next-line camelcase */
  const { site_name, support_email } = useSettings()
  return (
    <div className="contact-support">
      {isError ? (
        <h3 className="error-label">
          Sorry, there was an error sending the email.
        </h3>
      ) : (
        <>
          <hr />
          <b>Still no password reset email? </b>
        </>
      )}
      {/* eslint-disable-next-line camelcase */}
      Please {isError ? "try again or" : ""} contact our {` ${site_name} `}
      {/* eslint-disable-next-line camelcase */}
      <a href={`mailto:${support_email}`}>Customer Support Center.</a>
      <br />
      <br />
    </div>
  )
}

export default function LoginForgotPasswordPage() {
  const [isSent, setIsSent] = useState(false)
  const [isError, setIsError] = useState(false)
  const [email, setEmail] = useState<string | null>(null)
  const [, forgotPassword] = useMutation(auth.forgotPasswordMutation)
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()

  const reset = useCallback(() => {
    setIsSent(false)
    setIsError(false)
    setEmail(null)
  }, [])

  const onSubmit = useCallback(
    async (
      { email }: EmailFormValues,
      { setSubmitting }: FormikActions<EmailFormValues>
    ) => {
      try {
        const resp = await forgotPassword(email)

        const isSuccess = isSuccessResponse(resp)

        setIsSent(isSuccess)
        setIsError(!isSuccess)
        setEmail(email)
      } catch (e) {
        setIsError(true)
        throw e
      } finally {
        setSubmitting(false)
      }
    },
    []
  )

  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${FORGOT_PASSWORD_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1>{isSent ? "Forgot Password" : "Password reset!"}</h1>
          </div>
          {isSent ? (
            <React.Fragment>
              {email && <PasswordResetText email={email} />}
              <p>
                <b>
                  If you do NOT receive your password reset email, here's what
                  to do:
                </b>
              </p>
              <ul>
                <li>
                  <b>Wait a few moments.</b> It might take several minutes to
                  receive your password reset email.
                </li>
                <li>
                  <b>Check your spam folder.</b> It might be there.
                </li>
                <li>
                  <b>Is your email correct?</b> If you made a typo, no problem,
                  try{" "}
                  <Link to={routes.login.forgot.begin} onClick={reset}>
                    resetting your password
                  </Link>{" "}
                  again.
                </li>
              </ul>
              <CustomerSupport isError={false} />
            </React.Fragment>
          ) : (
            <React.Fragment>
              {isError ? (
                <CustomerSupport isError={true} />
              ) : (
                <p>Enter your email to receive a password reset link.</p>
              )}
              <EmailForm onSubmit={onSubmit} />
            </React.Fragment>
          )}
        </div>
      </div>
    </DocumentTitle>
  )
}
