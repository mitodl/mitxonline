// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { connect } from "react-redux"
import { createStructuredSelector } from "reselect"
import { Link } from "react-router-dom"

import { REGISTER_CONFIRM_PAGE_TITLE } from "../../../constants"
import { routes } from "../../../lib/urls"
import { qsEmailSelector } from "../../../lib/selectors"

type Props = {|
  params: { email: ?string }
|}

export class RegisterConfirmSentPage extends React.Component<Props> {
  render() {
    const {
      params: { email }
    } = this.props

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${REGISTER_CONFIRM_PAGE_TITLE}`}
      >
        <div className="std-page-body container auth-page">
          <div className="auth-card card-shadow auth-form">
            <div className="auth-header">
              <h1>Thank you!</h1>
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
              Please contact our {` ${SETTINGS.site_name} `}
              <a href={`mailto:${SETTINGS.support_email}`}>
                Customer Support Center.
              </a>
              <br />
              <br />
            </div>
          </div>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  params: createStructuredSelector({ email: qsEmailSelector })
})

export default connect(mapStateToProps)(RegisterConfirmSentPage)
