// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { Formik, Form } from "formik"
import { REGISTER_EXTRA_DETAILS_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync, requestAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { createStructuredSelector } from "reselect"
import { routes } from "../../../lib/urls"

import { qsNextSelector } from "../../../lib/selectors"

import users, { currentUserSelector } from "../../../lib/queries/users"
import queries from "../../../lib/queries"

import {
  addlProfileFieldsValidation,
  AddlProfileFields
} from "../../../components/forms/ProfileFormFields"

import type { HttpResponse } from "../../../flow/httpTypes"
import type { User } from "../../../flow/authTypes"
import { addUserNotification } from "../../../actions"

type StateProps = {|
  currentUser: User
|}

type DispatchProps = {|
  editProfile: (userProfileData: User) => Promise<HttpResponse<User>>,
  getCurrentUser: () => Promise<HttpResponse<User>>
|}

type Props = {
  params: { next: string },
  ...StateProps,
  ...DispatchProps
}

const getInitialValues = (user: User) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address,
  user_profile:  user.user_profile
})

export class RegisterAdditionalDetailsPage extends React.Component<Props> {
  async onSubmit(detailsData: any, { setSubmitting, setErrors }: any) {
    const {
      editProfile,
      params: { next }
    } = this.props

    // On this page, if the user selects stuff for learner type and education
    // level, we also set the field flag so we don't ping the learner later to
    // fill in data.

    if (
      detailsData.user_profile.highest_education !== "" &&
      (detailsData.user_profile.type_is_educator ||
        detailsData.user_profile.type_is_other ||
        detailsData.user_profile.type_is_professional ||
        detailsData.user_profile.type_is_student)
    ) {
      detailsData.user_profile.addl_field_flag = true
    }

    try {
      const { body }: { body: Object } = await editProfile(detailsData)
      if (body.errors && body.errors.length > 0) {
        setErrors(body.errors)
      } else {
        if (next) {
          window.location = next
        } else {
          window.location = routes.dashboard
        }
      }
    } finally {
      setSubmitting(false)
    }
  }

  render() {
    const { currentUser } = this.props

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${REGISTER_EXTRA_DETAILS_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page registration-page">
          <div className="std-card std-card-auth">
            <div className="std-card-body">
              <h2>About You</h2>
              <div className="form-group">
                Please tell us a bit about yourself. The data you provide here
                will assist us in our research pursuits. All fields are
                optional.
              </div>
              <hr className="hr-class-margin" />
              <div className="auth-form">
                <Formik
                  onSubmit={this.onSubmit.bind(this)}
                  validationSchema={addlProfileFieldsValidation}
                  initialValues={getInitialValues(currentUser)}
                >
                  {({ isSubmitting, values }) => {
                    return (
                      <Form>
                        <AddlProfileFields
                          values={values}
                          isNewAccount={false}
                        />
                        <div className="submit-row">
                          <button
                            type="submit"
                            className="btn btn-primary btn-gradient-red-to-blue"
                            disabled={isSubmitting}
                          >
                            Submit
                          </button>
                        </div>
                      </Form>
                    )
                  }}
                </Formik>
              </div>
            </div>
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  currentUser: currentUserSelector,
  params:      createStructuredSelector({
    next: qsNextSelector
  })
})

const mapPropsToConfig = () => [queries.users.countriesQuery()]

const editProfile = (userProfileData: User) =>
  mutateAsync(users.editProfileMutation(userProfileData))

const getCurrentUser = () =>
  requestAsync({
    ...users.currentUserQuery(),
    force: true
  })

const mapDispatchToProps = {
  editProfile,
  getCurrentUser,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(RegisterAdditionalDetailsPage)
