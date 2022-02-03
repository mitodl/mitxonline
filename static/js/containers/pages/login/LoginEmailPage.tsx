import { FormikActions } from "formik"
import React, { useCallback } from "react"
import DocumentTitle from "react-document-title"
import { useHistory, useLocation } from "react-router"
import { Link } from "react-router-dom"
import { mutateAsync, QueryResponse } from "redux-query"
import { useMutation } from "redux-query-react"
import EmailForm from "../../../components/forms/EmailForm"
import { LOGIN_EMAIL_PAGE_TITLE } from "../../../constants"
import useSettings from "../../../hooks/settings"
import {
  handleAuthResponse,
  STATE_ERROR,
  STATE_REGISTER_REQUIRED
} from "../../../lib/auth"
import * as auth from "../../../lib/queries/auth"
import { getNextParam, routes } from "../../../lib/urls"
import { AuthResponse, EmailFormValues } from "../../../types/auth"

export default function LoginEmailPage() {
  const location = useLocation()
  const history = useHistory()
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()

  const [
    ,
    loginEmail
  ] = useMutation((email: string, nextUrl: string | null | undefined) =>
    mutateAsync(auth.loginEmailMutation(email, nextUrl))
  )

  const onSubmit = useCallback(
    async (
      { email }: EmailFormValues,
      { setSubmitting, setErrors }: FormikActions<EmailFormValues>
    ) => {
      const nextUrl = getNextParam(location.search) as string

      try {
        const { body } = (await loginEmail(
          email,
          nextUrl
        )) as QueryResponse<AuthResponse>
        handleAuthResponse(history, body, {
          // eslint-disable-next-line camelcase
          [STATE_ERROR]: ({ field_errors }: AuthResponse) =>
            setErrors(field_errors),
          // eslint-disable-next-line camelcase
          [STATE_REGISTER_REQUIRED]: ({ field_errors }: AuthResponse) =>
            setErrors(field_errors)
        })
      } finally {
        setSubmitting(false)
      }
    },
    [location]
  )

  const link = `${routes.register.begin}${location.search}`
  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${LOGIN_EMAIL_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1>Sign in</h1>
          </div>
          <EmailForm onSubmit={onSubmit}>
            <React.Fragment>
              <span>Don't have an account? </span>
              <Link to={link} className="link-black">
                Create Account
              </Link>
            </React.Fragment>
          </EmailForm>
        </div>
      </div>
    </DocumentTitle>
  )
}
