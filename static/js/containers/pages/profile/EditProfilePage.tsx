import React, { useCallback } from "react"
import DocumentTitle from "react-document-title"
import { useHistory } from "react-router"
import { QueryResponse } from "redux-query"
import { useMutation } from "redux-query-react"
import EditProfileForm from "../../../components/forms/EditProfileForm"
import { EDIT_PROFILE_PAGE_TITLE } from "../../../constants"
import useSettings from "../../../hooks/settings"
import { useLoggedInUser } from "../../../hooks/user"
import * as users from "../../../lib/queries/users"
import { routes } from "../../../lib/urls"
import { EditUserProfileForm } from "../../../types/auth"

export default function EditProfilePage() {
  const user = useLoggedInUser()
  const history = useHistory()
  const [, editProfile] = useMutation(users.editProfileMutation)
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()

  const onSubmit = useCallback(
    async (
      profileData: EditUserProfileForm,
      { setSubmitting, setErrors }: Record<string, any>
    ) => {
      try {
        const {
          body: { errors }
        } = (await editProfile(profileData)) as QueryResponse

        if (errors && errors.length > 0) {
          setErrors({
            email: errors[0]
          })
        } else {
          history.push(routes.profile)
        }
      } finally {
        setSubmitting(false)
      }
    },
    []
  )

  return user ? (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${EDIT_PROFILE_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1>Edit Profile</h1>
          </div>
          <EditProfileForm user={user} onSubmit={onSubmit} />
        </div>
      </div>
    </DocumentTitle>
  ) : null
}
