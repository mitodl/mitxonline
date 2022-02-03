import React, { useCallback, useEffect } from "react"
import DocumentTitle from "react-document-title"
import { useSelector } from "react-redux"
import { useHistory } from "react-router"
import { QueryResponse } from "redux-query"
import { useMutation } from "redux-query-react"
import LoginPasswordForm from "../../../components/forms/LoginPasswordForm"
import { LOGIN_PASSWORD_PAGE_TITLE } from "../../../constants"
import useSettings from "../../../hooks/settings"
import { handleAuthResponse, STATE_ERROR } from "../../../lib/auth"
import { authSelector, loginPasswordMutation } from "../../../lib/queries/auth"
import { routes } from "../../../lib/urls"
import { AuthResponse, PasswordFormValues } from "../../../types/auth"

export default function LoginPasswordPage() {
  const history = useHistory()
  const auth = useSelector(authSelector)
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()

  const [
    ,
    loginPassword
  ] = useMutation((password: string, partialToken: string) =>
    loginPasswordMutation(password, partialToken)
  )

  useEffect(() => {
    /* eslint-disable-next-line camelcase */
    if (!auth || !auth.partial_token) {
      // if there's no partialToken in the state
      // this page was navigated to directly and login needs to be started over
      history.push(routes.login.begin)
    }
  }, [])

  const onSubmit = useCallback(
    async (
      { password }: PasswordFormValues,
      { setSubmitting, setErrors }: any
    ) => {
      /* eslint-disable-next-line camelcase */
      const { partial_token } = auth

      /* eslint-disable-next-line camelcase */
      if (!partial_token) {
        throw Error("Invalid state: password page with no partialToken")
      }

      try {
        const resp = (await loginPassword(
          password,
          partial_token
        )) as QueryResponse<AuthResponse>
        handleAuthResponse(history, resp.body, {
          /* eslint-disable-next-line camelcase */
          [STATE_ERROR]: ({ field_errors }: AuthResponse) =>
            /* eslint-disable-next-line camelcase */
            setErrors(field_errors)
        })
      } finally {
        setSubmitting(false)
      }
    },
    []
  )

  const name = auth?.extra_data?.name
  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${LOGIN_PASSWORD_PAGE_TITLE}`}>
      {auth ? (
        <div className="std-page-body container auth-page">
          <div className="auth-card card-shadow auth-form">
            <div className="auth-header">
              <h1>Sign in</h1>
              {name && (
                <p>
                  Signing in as <b>{name}</b>
                </p>
              )}
            </div>
            <LoginPasswordForm onSubmit={onSubmit} />
          </div>
        </div>
      ) : (
        <div />
      )}
    </DocumentTitle>
  )
}
