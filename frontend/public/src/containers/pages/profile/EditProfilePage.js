// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { EDIT_PROFILE_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync, requestAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { createStructuredSelector } from "reselect"

import users, { currentUserSelector } from "../../../lib/queries/users"
import queries from "../../../lib/queries"
import EditProfileForm from "../../../components/forms/EditProfileForm"

import type { HttpResponse } from "../../../flow/httpTypes"
import type { Country, User } from "../../../flow/authTypes"
import type { RouterHistory } from "react-router"

type StateProps = {|
  countries: ?Array<Country>,
  currentUser: User
|}

type DispatchProps = {|
  editProfile: (userProfileData: User) => Promise<HttpResponse<User>>,
  getCurrentUser: () => Promise<HttpResponse<User>>
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
    if (profileData.user_profile) {
      profileData.user_profile.addl_field_flag = true
    }

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
        <>{ currentUser ? <div role="banner" className="std-page-header">
          <h1>{EDIT_PROFILE_PAGE_TITLE}</h1>
        </div> : null }
        <div className="std-page-body container auth-page">
          <div className="std-card std-card-auth">
            <div className="std-card-body edit-profile-page">
              <h1>Profile Information</h1>
              <EditProfileForm
                countries={countries}
                user={currentUser}
                onSubmit={this.onSubmit.bind(this)}
              />
            </div>
          </div>
        </div></>
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
