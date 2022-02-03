import React from "react"
import DocumentTitle from "react-document-title"
import { REGISTER_DENIED_PAGE_TITLE } from "../../../constants"
import useQueryString from "../../../hooks/querystring"
import useSettings from "../../../hooks/settings"

export default function RegisterDeniedPage() {
  /* eslint-disable-next-line camelcase */
  const { support_email, site_name } = useSettings()
  const { error } = useQueryString<{ error: string }>()
  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${REGISTER_DENIED_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="register-error-icon" />
          <p>Sorry, we cannot create an account for you at this time.</p>
          {error ? <p className="error-detail">{error}</p> : null}
          <p>
            Please contact us at {/* eslint-disable-next-line camelcase */}
            <a href={`mailto:${support_email}`}>{support_email}</a>
          </p>
        </div>
      </div>
    </DocumentTitle>
  )
}
