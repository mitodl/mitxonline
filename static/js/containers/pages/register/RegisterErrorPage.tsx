import React from "react"
import DocumentTitle from "react-document-title"
import { REGISTER_ERROR_PAGE_TITLE } from "../../../constants"
import useSettings from "../../../hooks/settings"

export default function RegisterErrorPage() {
  /* eslint-disable-next-line camelcase */
  const { site_name, support_email } = useSettings()
  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${REGISTER_ERROR_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="register-error-icon" />
          <p>Sorry, we cannot create an account for you at this time.</p>
          <p>
            Please try again later or contact us at{" "}
            {/* eslint-disable-next-line camelcase */}
            <a href={`mailto:${support_email}`}>{support_email}</a>
          </p>
        </div>
      </div>
    </DocumentTitle>
  )
}
