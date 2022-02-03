import React, { useEffect } from "react"
import DocumentTitle from "react-document-title"
import { useSelector } from "react-redux"
import { useHistory } from "react-router"
import { Link } from "react-router-dom"
import { useMutation } from "redux-query-react"
import {
  ALERT_TYPE_TEXT,
  REGISTER_CONFIRM_PAGE_TITLE
} from "../../../constants"
import { useNotifications } from "../../../hooks/notifications"
import useQueryString from "../../../hooks/querystring"
import useSettings from "../../../hooks/settings"
import {
  handleAuthResponse,
  INFORMATIVE_STATES,
  STATE_EXISTING_ACCOUNT,
  STATE_INVALID_EMAIL,
  STATE_INVALID_LINK,
  STATE_REGISTER_DETAILS
} from "../../../lib/auth"
import {
  authSelector,
  registerConfirmEmailMutation
} from "../../../lib/queries/auth"
import { routes } from "../../../lib/urls"
import { AuthResponse } from "../../../types/auth"

export default function RegisterConfirmPage() {
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()
  const history = useHistory()
  const { addNotification } = useNotifications()
  const auth = useSelector<any, AuthResponse>(authSelector)
  const qsParams = useQueryString()
  const [, registerConfirmEmail] = useMutation(registerConfirmEmailMutation)

  useEffect(() => {
    registerConfirmEmail(qsParams)
  }, [])

  useEffect(() => {
    if (!auth?.state) return

    handleAuthResponse(history, auth, {
      [STATE_REGISTER_DETAILS]: () => {
        addNotification("email-verified", {
          type:  ALERT_TYPE_TEXT,
          props: {
            text:
              "Success! We've verified your email. Please finish your account creation below."
          }
        })
      }
    })
  }, [auth?.state])

  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${REGISTER_CONFIRM_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        {auth && INFORMATIVE_STATES.indexOf(auth.state) > -1 ? (
          getAppropriateInformationFragment(auth.state)
        ) : (
          <p>Confirming...</p>
        )}
      </div>
    </DocumentTitle>
  )
}

const getAppropriateInformationFragment = (state: string) => {
  let preLinkText = ""
  let postLinkText = ""
  let linkRoute = null

  if (state === STATE_INVALID_LINK) {
    preLinkText = "This invitation is invalid or has expired. Please"
    postLinkText = "to register again"
    linkRoute = routes.register.begin
  } else if (state === STATE_EXISTING_ACCOUNT) {
    preLinkText = "You already have an mitX Online account. Please"
    postLinkText = "to sign in"
    linkRoute = routes.login.begin
  } else if (state === STATE_INVALID_EMAIL) {
    preLinkText = "No confirmation code was provided or it has expired. Please"
    postLinkText = "to register again"
    linkRoute = routes.register.begin
  }

  return linkRoute ? (
    <React.Fragment>
      <span className={"confirmation-message"}>
        {preLinkText}{" "}
        <Link className={"action-link"} to={linkRoute}>
          click here {postLinkText}
        </Link>
        .
      </span>
    </React.Fragment>
  ) : null
}
