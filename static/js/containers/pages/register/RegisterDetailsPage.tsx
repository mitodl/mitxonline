import { FormikActions } from "formik"
import React, { useCallback } from "react"
import DocumentTitle from "react-document-title"
import { useHistory } from "react-router"
import { Link } from "react-router-dom"
import { QueryResponse } from "redux-query"
import { useMutation } from "redux-query-react"
import RegisterDetailsForm from "../../../components/forms/RegisterDetailsForm"
import { REGISTER_DETAILS_PAGE_TITLE } from "../../../constants"
import useQueryString from "../../../hooks/querystring"
import useSettings from "../../../hooks/settings"
import {
  handleAuthResponse,
  STATE_ERROR,
  STATE_REGISTER_DETAILS
} from "../../../lib/auth"
import * as auth from "../../../lib/queries/auth"
import { routes } from "../../../lib/urls"
import { AuthResponse, CreateUserProfileForm } from "../../../types/auth"

export default function RegisterDetailsPage() {
  /* eslint-disable camelcase */
  const { site_name } = useSettings()
  const { partial_token: partialToken } = useQueryString<{
    partial_token: string
  }>()
  /* eslint-enable camelcase */
  const history = useHistory()
  const [, registerDetails] = useMutation(auth.registerDetailsMutation)

  /* eslint-disable camelcase */
  const onSubmit = useCallback(
    async (
      { name, password, username, legal_address }: CreateUserProfileForm,
      { setSubmitting, setErrors }: FormikActions<CreateUserProfileForm>
    ) => {
      try {
        const { body } = (await registerDetails(
          name,
          password,
          username,
          legal_address,
          partialToken
        )) as QueryResponse<AuthResponse>

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
      } finally {
        setSubmitting(false)
      }
    },
    [partialToken, history]
  )
  /* eslint-enable camelcase */

  return partialToken ? (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${REGISTER_DETAILS_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page registration-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1>Create an Account</h1>
          </div>
          <div className="form-group">
            {/* eslint-disable-next-line camelcase */}
            {`Already have an ${site_name} account? `}
            <Link className="link-black" to={routes.login.begin}>
              Sign in to your account
            </Link>
          </div>
          <hr className="hr-class-margin" />
          <div className="auth-form">
            <RegisterDetailsForm onSubmit={onSubmit} />
          </div>
        </div>
      </div>
    </DocumentTitle>
  ) : null
}
