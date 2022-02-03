import React, { useEffect, useRef } from "react"
import DocumentTitle from "react-document-title"
import { Link } from "react-router-dom"
import { REGISTER_CONFIRM_PAGE_TITLE } from "../../../constants"
import useQueryString from "../../../hooks/querystring"
import useSettings from "../../../hooks/settings"
import { routes } from "../../../lib/urls"

export default function RegisterConfirmSentPage() {
  /* eslint-disable-next-line camelcase */
  const { support_email, site_name } = useSettings()
  const { email } = useQueryString<{ email: string }>()
  const headingRef = useRef<HTMLHeadingElement>(null)

  useEffect(() => {
    if (headingRef.current) {
      headingRef.current.focus()
    }
  }, [headingRef])

  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${REGISTER_CONFIRM_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="auth-card card-shadow auth-form">
          <div className="auth-header">
            <h1 tabIndex={0} ref={headingRef}>
              Thank you!
            </h1>
          </div>
          <p>
            We sent an email to <b>{email}</b>, please verify your address to
            continue.
          </p>
          <p>
            <b>
              If you do NOT receive your password reset email, here's what to
              do:
            </b>
          </p>
          <ul>
            <li>
              <b>Wait a few moments.</b> It might take several minutes to
              receive your password reset email.
            </li>
            <li>
              <b>Check your spam folder.</b> It might be there.
            </li>
            <li>
              <b>Is your email correct?</b> If you made a typo, no problem,{" "}
              <Link to={routes.register.begin}>create an account</Link> again.
            </li>
          </ul>
          <div className="contact-support">
            <hr />
            <b>Still no password reset email? </b>
            <br />
            {/* eslint-disable-next-line camelcase */}
            Please contact our {` ${site_name} `}
            {/* eslint-disable-next-line camelcase */}
            <a href={`mailto:${support_email}`}>Customer Support Center.</a>
            <br />
            <br />
          </div>
        </div>
      </div>
    </DocumentTitle>
  )
}
