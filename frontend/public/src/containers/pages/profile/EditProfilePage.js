// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { EDIT_PROFILE_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest, mutateAsync, requestAsync } from "redux-query"
import { createStructuredSelector } from "reselect"

import users, { currentUserSelector } from "../../../lib/queries/users"
import queries from "../../../lib/queries"
import EditProfileForm from "../../../components/forms/EditProfileForm"

import type { Response } from "redux-query"
import type { Country, User } from "../../../flow/authTypes"
import type { RouterHistory } from "react-router"

type StateProps = {|
  countries: ?Array<Country>,
  currentUser: User
|}

type DispatchProps = {|
  editProfile: (userProfileData: User) => Promise<Response<User>>,
  getCurrentUser: () => Promise<Response<User>>
|}

type ProfileProps = {|
  history: RouterHistory
|}

type Props = {|
  ...StateProps,
  ...DispatchProps,
  ...ProfileProps
|}

export class EditProfilePage extends React.Component<Props> {
  async onSubmit(profileData: User, { setSubmitting, setErrors }: Object) {
    const { editProfile } = this.props

    // setting this to true if you edit your profile at all
    profileData.user_profile.addl_field_flag = true

    try {
      const {
        body: { errors }
      }: { body: Object } = await editProfile(profileData)

      if (errors && errors.length > 0) {
        setErrors({
          email: errors[0]
        })
      } else {
        window.location.reload()
      }
    } finally {
      setSubmitting(false)
    }
  }

  render() {
    const { countries, currentUser } = this.props
    return countries ? (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${EDIT_PROFILE_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page">
          <div className="auth-card card-shadow auth-form">
            <div className="auth-header">
              <h1>Edit Profile</h1>
            </div>
            <EditProfileForm
              countries={countries}
              user={currentUser}
              onSubmit={this.onSubmit.bind(this)}
            />
          </div>
        </div>
      </DocumentTitle>
    ) : null
  }
}

const editProfile = (userProfileData: User) =>
  mutateAsync(users.editProfileMutation(userProfileData))

const getCurrentUser = () =>
  requestAsync({
    ...users.currentUserQuery(),
    force: true
  })

const mapStateToProps = createStructuredSelector({
  currentUser: currentUserSelector,
  countries:   queries.users.countriesSelector
})

const mapDispatchToProps = {
  editProfile: editProfile,
  getCurrentUser
}

const mapPropsToConfigs = () => [queries.users.countriesQuery()]

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfigs)
)(EditProfilePage)
