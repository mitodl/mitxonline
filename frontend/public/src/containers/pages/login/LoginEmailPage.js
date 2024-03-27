// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { LOGIN_EMAIL_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync } from "redux-query"

import auth from "../../../lib/queries/auth"
import { routes, getNextParam } from "../../../lib/urls"
import {
  STATE_ERROR,
  STATE_REGISTER_REQUIRED,
  handleAuthResponse
} from "../../../lib/auth"

import EmailForm from "../../../components/forms/EmailForm"

import type { RouterHistory, Location } from "react-router"

import type { HttpResponse } from "../../../flow/httpTypes"
import type { AuthResponse, EmailFormValues } from "../../../flow/authTypes"
import { Link } from "react-router-dom"

type Props = {
  location: Location,
  history: RouterHistory,
  loginEmail: (
    email: string,
    next: ?string
  ) => Promise<HttpResponse<AuthResponse>>
}

export class LoginEmailPage extends React.Component<Props> {
  async onSubmit(
    { email }: EmailFormValues,
    { setSubmitting, setErrors }: any
  ) {
    const { loginEmail, location, history } = this.props
    const nextUrl = getNextParam(location.search)

    try {
      const { body } = await loginEmail(email, nextUrl)

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
  }

  render() {
    const link = `${routes.register.begin}${this.props.location.search}`

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${LOGIN_EMAIL_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page">
          <div className="std-card std-card-auth">
            <div className="std-card-body">
              <h1>Sign in</h1>
              <EmailForm onSubmit={this.onSubmit.bind(this)}>
                <div>
                  <p>
                    <span>Don't have an account? </span>
                    <Link to={link} className="link-black">
                      Create Account
                    </Link>
                  </p>
                </div>
              </EmailForm>
            </div>
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const loginEmail = (email: string, nextUrl: ?string) =>
  mutateAsync(auth.loginEmailMutation(email, nextUrl))

const mapDispatchToProps = {
  loginEmail
}

export default compose(connect(null, mapDispatchToProps))(LoginEmailPage)
