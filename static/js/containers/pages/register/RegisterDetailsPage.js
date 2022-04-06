// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { REGISTER_DETAILS_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { Link } from "react-router-dom"
import { connectRequest, mutateAsync, requestAsync } from "redux-query"
import { createStructuredSelector } from "reselect"

import auth from "../../../lib/queries/auth"
import users from "../../../lib/queries/users"
import { routes } from "../../../lib/urls"
import {
  STATE_ERROR,
  handleAuthResponse,
  STATE_REGISTER_DETAILS
} from "../../../lib/auth"
import queries from "../../../lib/queries"
import { qsPartialTokenSelector } from "../../../lib/selectors"

import RegisterDetailsForm from "../../../components/forms/RegisterDetailsForm"

import type { RouterHistory, Location } from "react-router"
import type { Response } from "redux-query"
import type {
  AuthResponse,
  LegalAddress,
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
    partialToken: string
  ) => Promise<Response<AuthResponse>>,
  getCurrentUser: () => Promise<Response<User>>
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
      params: { partialToken }
    } = this.props

    try {
      const { body } = await registerDetails(
        detailsData.name,
        detailsData.password,
        detailsData.username,
        detailsData.legal_address,
        partialToken
      )

      /* eslint-disable camelcase */
      handleAuthResponse(history, body, {
        [STATE_ERROR]: ({ field_errors }: AuthResponse) =>
          setErrors(field_errors),
        [STATE_REGISTER_DETAILS]: ({ field_errors }: AuthResponse) => {
          // Validation failures will result in a 200 API response that still points to this page but contains
          // field errors.
          if (field_errors) {
            setErrors(field_errors)
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
  partialToken: string
) =>
  mutateAsync(
    auth.registerDetailsMutation(
      name,
      password,
      username,
      legalAddress,
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
  getCurrentUser
}

export default compose(
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(RegisterDetailsPage)
