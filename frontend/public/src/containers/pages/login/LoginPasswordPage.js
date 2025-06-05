// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { LOGIN_PASSWORD_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync, requestAsync } from "redux-query"
import { createStructuredSelector } from "reselect"

import auth, { authSelector } from "../../../lib/queries/auth"
import users from "../../../lib/queries/users"
import { routes } from "../../../lib/urls"
import { STATE_ERROR, handleAuthResponse } from "../../../lib/auth"

import LoginPasswordForm from "../../../components/forms/LoginPasswordForm"

import type { RouterHistory, Location } from "react-router"
import type {
  AuthResponse,
  User,
  PasswordFormValues
} from "../../../flow/authTypes"
import type { HttpResponse } from "../../../flow/httpTypes"

type Props = {
  location: Location,
  history: RouterHistory,
  auth: AuthResponse,
  loginPassword: (
    password: string,
    partialToken: string
  ) => Promise<HttpResponse<AuthResponse>>,
  getCurrentUser: () => Promise<HttpResponse<User>>
}

export class LoginPasswordPage extends React.Component<Props> {
  componentDidMount() {
    const { history, auth } = this.props

    if (!auth || !auth.partial_token) {
      // if there's no partialToken in the state
      // this page was navigated to directly and login needs to be started over
      history.push(routes.login.begin)
    }
  }

  async onSubmit(
    { password }: PasswordFormValues,
    { setSubmitting, setErrors }: any
  ) {
    /* eslint-disable camelcase */
    const {
      loginPassword,
      history,
      auth: { partial_token }
    } = this.props

    if (!partial_token) {
      throw Error("Invalid state: password page with no partialToken")
    }

    try {
      const { body } = await loginPassword(password, partial_token)

      handleAuthResponse(history, body, {
        [STATE_ERROR]: ({ field_errors }: AuthResponse) =>
          setErrors(field_errors)
      })
    } finally {
      setSubmitting(false)
    }
    /* eslint-enable camelcase */
  }

  render() {
    const { auth } = this.props

    if (!auth) {
      return (
        <DocumentTitle
          title={`${SETTINGS.site_name} | ${LOGIN_PASSWORD_PAGE_TITLE}`}
        >
          <div />
        </DocumentTitle>
      )
    }

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${LOGIN_PASSWORD_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page">
          <div className="std-card std-card-auth">
            <div className="std-card-body">
              <h1>Sign in</h1>
              <LoginPasswordForm onSubmit={this.onSubmit.bind(this)} />
            </div>
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  auth: authSelector
})

const loginPassword = (password: string, partialToken: string) =>
  mutateAsync(auth.loginPasswordMutation(password, partialToken))

const getCurrentUser = () =>
  requestAsync({
    ...users.currentUserQuery(),
    force: true
  })

const mapDispatchToProps = {
  loginPassword,
  getCurrentUser
}

export default compose(connect(mapStateToProps, mapDispatchToProps))(
  LoginPasswordPage
)
