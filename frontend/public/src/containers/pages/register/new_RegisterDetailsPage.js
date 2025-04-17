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
import { mutateAsync, requestAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { createStructuredSelector } from "reselect"

import auth from "../../../lib/queries/new_auth"
import users from "../../../lib/queries/users"
import { routes } from "../../../lib/urls"
import {
  STATE_ERROR,
  handleAuthResponse,
  STATE_REGISTER_DETAILS,
  STATE_SUCCESS
} from "../../../lib/auth"
import queries from "../../../lib/queries"

import RegisterDetailsForm from "../../../components/forms/new_RegisterDetailsForm"
import { addUserNotification } from "../../../actions"

import type { RouterHistory, Location } from "react-router"
import type { HttpResponse } from "../../../flow/httpTypes"
import type {
  LegalAddress,
  UserProfile,
  User,
  Country
} from "../../../flow/authTypes"

type RegisterProps = {|
  location: Location,
  history: RouterHistory
|}

type StateProps = {|
  countries: Array<Country>
|}

type DispatchProps = {|
  registerDetails: (
    name: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: UserProfile
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
    const { history, registerDetails, addUserNotification } = this.props

    try {
      const { body } = await registerDetails(
        detailsData.name,
        detailsData.username,
        detailsData.legal_address,
        detailsData.user_profile
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
        const nextParam = body.redirect_url
        body.redirect_url = routes.register.additionalDetails
        if (nextParam) {
          body.redirect_url += `?next=${encodeURIComponent(nextParam)}`
        }
      }
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
          <div className="std-card std-card-auth">
            <div className="std-card-body create-account-page">
              <h2>Provide Profile Information</h2>
              <hr className="hr-class-margin" />
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
  countries: queries.users.countriesSelector
})

const mapPropsToConfig = () => [queries.users.countriesQuery()]

const registerDetails = (
  name: string,
  username: string,
  legalAddress: LegalAddress,
  userProfile: UserProfile
) =>
  mutateAsync(
    auth.registerDetailsMutation(name, username, legalAddress, userProfile)
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
