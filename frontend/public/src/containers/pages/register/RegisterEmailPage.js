// @flow
/* global SETTINGS: false */
import qs from "query-string"
import React from "react"
import DocumentTitle from "react-document-title"
import { REGISTER_EMAIL_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync } from "redux-query"
import { createStructuredSelector } from "reselect"

import { addUserNotification } from "../../../actions"

import queries from "../../../lib/queries"
import {
  STATE_ERROR,
  STATE_REGISTER_CONFIRM_SENT,
  STATE_LOGIN_PASSWORD,
  STATE_REGISTER_EMAIL,
  handleAuthResponse,
  generateLoginRedirectUrl
} from "../../../lib/auth"
import { qsNextSelector } from "../../../lib/selectors"
import { currentUserSelector } from "../../../lib/queries/users"
import { ALERT_TYPE_TEXT } from "../../../constants"

import RegisterEmailForm from "../../../components/forms/RegisterEmailForm"

import { routes } from "../../../lib/urls"

import type { RouterHistory, Location } from "react-router"
import type { HttpResponse } from "../../../flow/httpTypes"
import type { AuthResponse } from "../../../flow/authTypes"
import type { RegisterEmailFormValues } from "../../../components/forms/RegisterEmailForm"

type Props = {
  location: Location,
  history: RouterHistory,
  params: { next: string },
  registerEmail: (
    email: string,
    recaptcha: ?string,
    next: ?string
  ) => Promise<HttpResponse<AuthResponse>>,
  addUserNotification: Function,
  currentUser: ?Object
}

const accountExistsNotificationText = (email: string): string =>
  `You already have an account with ${email}. Enter password to sign in.`
export class RegisterEmailPage extends React.Component<Props> {
  componentDidMount() {
    // If OIDC login is disabled but API gateway is enabled
    if (!SETTINGS.oidc_login_url && SETTINGS.api_gateway_enabled) {
      const { currentUser } = this.props
      if (currentUser && currentUser.is_authenticated) {
        // Redirect logged-in users to dashboard
        window.location.replace(routes.dashboard)
      } else {
        // Redirect others to login page
        generateLoginRedirectUrl()
      }
      return
    }
  }

  async onSubmit(
    { email, recaptcha }: RegisterEmailFormValues,
    { setSubmitting, setErrors }: any
  ) {
    const {
      addUserNotification,
      registerEmail,
      params: { next },
      history
    } = this.props

    try {
      const { body } = await registerEmail(email, recaptcha, next)

      handleAuthResponse(history, body, {
        [STATE_REGISTER_CONFIRM_SENT]: () => {
          const params = qs.stringify({
            email
          })
          history.push(`${routes.register.confirmSent}?${params}`)
        },

        [STATE_REGISTER_EMAIL]: () => {
          addUserNotification({
            "account-blocked": {
              type:  ALERT_TYPE_TEXT,
              color: "danger",
              props: {
                text: [
                  <div key="1">
                    Please contact{" "}
                    <a
                      style={{ color: "white", textDecoration: "underline" }}
                      href={""}
                    >
                      {" "}
                      customer support
                    </a>{" "}
                    to complete your registration.
                  </div>
                ]
              }
            }
          })
        },
        [STATE_LOGIN_PASSWORD]: () => {
          addUserNotification({
            "account-exists": {
              type:  ALERT_TYPE_TEXT,
              color: "danger",
              props: {
                text: accountExistsNotificationText(email)
              }
            }
          })
        },
        // eslint-disable-next-line camelcase
        [STATE_ERROR]: ({ field_errors }: AuthResponse) =>
          setErrors(field_errors)
      })
    } finally {
      setSubmitting(false)
    }
  }

  render() {
    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${REGISTER_EMAIL_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page">
          <div className="std-card std-card-auth">
            <div className="std-card-body">
              <h2>Create Account</h2>
              <RegisterEmailForm onSubmit={this.onSubmit.bind(this)} />
            </div>
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  params: createStructuredSelector({
    next: qsNextSelector
  }),
  currentUser: currentUserSelector
})

const registerEmail = (email: string, recaptcha: ?string, nextUrl: ?string) =>
  mutateAsync(queries.auth.registerEmailMutation(email, recaptcha, nextUrl))

const mapDispatchToProps = {
  registerEmail,
  addUserNotification
}

export default compose(connect(mapStateToProps, mapDispatchToProps))(
  RegisterEmailPage
)
