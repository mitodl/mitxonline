// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import {
  ALERT_TYPE_DANGER,
  REGISTER_DETAILS_PAGE_TITLE
} from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { Link } from "react-router-dom"
import { mutateAsync, requestAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { createStructuredSelector } from "reselect"

import auth from "../../../lib/queries/auth"
import users from "../../../lib/queries/users"
import { routes } from "../../../lib/urls"
import {
  STATE_ERROR,
  handleAuthResponse,
  STATE_REGISTER_DETAILS,
  STATE_SUCCESS
} from "../../../lib/auth"
import queries from "../../../lib/queries"
import { qsPartialTokenSelector } from "../../../lib/selectors"

import RegisterDetailsForm from "../../../components/forms/RegisterDetailsForm"
import { addUserNotification } from "../../../actions"

import type { RouterHistory, Location } from "react-router"
import type { HttpResponse } from "../../../flow/httpTypes"
import type {
  AuthResponse,
  LegalAddress,
  UserProfile,
  User,
  Country
} from "../../../flow/authTypes"

type RegisterProps = {|
  location: Location,
  history: RouterHistory,
  params: { partialToken: string }
|}

type StateProps = {|
  countries: Array<Country>
|}

type DispatchProps = {|
  registerDetails: (
    name: string,
    password: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: UserProfile,
    partialToken: string,
    next: ?string
  ) => Promise<HttpResponse<AuthResponse>>,
  getCurrentUser: () => Promise<HttpResponse<User>>,
  addUserNotification: Function
|}

type Props = {|
  ...RegisterProps,
  ...StateProps,
  ...DispatchProps
|}

export class RegisterDetailsPage extends React.Component<Props> {
  async onSubmit(detailsData: any, { setSubmitting, setErrors }: any) {
    const {
      history,
      registerDetails,
      params: { partialToken },
      addUserNotification
    } = this.props

    try {
      const { body } = await registerDetails(
        detailsData.name,
        detailsData.password,
        detailsData.username,
        detailsData.legal_address,
        detailsData.user_profile,
        partialToken
      )

      if (body.errors) {
        body.errors.forEach(error => {
          addUserNotification({
            "registration-failed-status": {
              type:  ALERT_TYPE_DANGER,
              props: {
                text: error
              }
            }
          })
        })
      }

      if (body.state === STATE_SUCCESS) {
        body.redirect_url = routes.register.additionalDetails
      }

      /* eslint-disable camelcase */
      handleAuthResponse(history, body, {
        [STATE_ERROR]: ({ field_errors }: AuthResponse) =>
          setErrors(field_errors),
        [STATE_REGISTER_DETAILS]: ({ field_errors }: AuthResponse) => {
          // Validation failures will result in a 200 API response that still points to this page but contains
          // field errors.
          if (field_errors) {
            setErrors(field_errors)

            if (field_errors["email"]) {
              addUserNotification({
                "registration-failed-status": {
                  type:  ALERT_TYPE_DANGER,
                  props: {
                    text: field_errors["email"]
                  }
                }
              })
            }
          }
        }
      })
      /* eslint-enable camelcase */
    } finally {
      setSubmitting(false)
    }
  }

  render() {
    const { countries } = this.props

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${REGISTER_DETAILS_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page registration-page">
          <div className="auth-card card-shadow auth-form">
            <div className="auth-header">
              <h1>Create an Account</h1>
            </div>
            <div className="form-group">
              {`Already have an ${SETTINGS.site_name} account? `}
              <Link className="link-black" to={routes.login.begin}>
                Sign in to your account
              </Link>
            </div>
            <hr className="hr-class-margin" />
            <div className="auth-form">
              <RegisterDetailsForm
                onSubmit={this.onSubmit.bind(this)}
                countries={countries}
              />
            </div>
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  params:    createStructuredSelector({ partialToken: qsPartialTokenSelector }),
  countries: queries.users.countriesSelector
})

const mapPropsToConfig = () => [queries.users.countriesQuery()]

const registerDetails = (
  name: string,
  password: string,
  username: string,
  legalAddress: LegalAddress,
  userProfile: UserProfile,
  partialToken: string
) =>
  mutateAsync(
    auth.registerDetailsMutation(
      name,
      password,
      username,
      legalAddress,
      userProfile,
      partialToken
    )
  )

const getCurrentUser = () =>
  requestAsync({
    ...users.currentUserQuery(),
    force: true
  })

const mapDispatchToProps = {
  registerDetails,
  getCurrentUser,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(RegisterDetailsPage)
