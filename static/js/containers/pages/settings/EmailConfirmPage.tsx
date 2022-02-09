import React, { useCallback, useEffect, useState } from "react"
import DocumentTitle from "react-document-title"
import { useHistory } from "react-router"
import { Link } from "react-router-dom"
import { useMutation, useRequest } from "redux-query-react"
import { ALERT_TYPE_TEXT, EMAIL_CONFIRM_PAGE_TITLE } from "../../../constants"
import { useNotifications } from "../../../hooks/notifications"
import useQueryString from "../../../hooks/querystring"
import useSettings from "../../../hooks/settings"
import queries from "../../../lib/queries"
import { routes } from "../../../lib/urls"

export default function EmailConfirmPage() {
  const [isConfirmed, setIsConfirmed] = useState(false)
  /* eslint-disable-next-line camelcase */
  const { site_name } = useSettings()
  const history = useHistory()
  const { addNotification } = useNotifications()
  /* eslint-disable-next-line camelcase */
  const { verification_code } = useQueryString<{ verification_code: string }>()

  const [
    { isPending, isFinished },
    confirmEmail
  ] = useMutation((code: string) => queries.auth.confirmEmailMutation(code))

  const [, refreshUser] = useRequest(queries.users.currentUserQuery())

  const confirmEmailAsync = useCallback(
    async (code: string) => {
      const result = await confirmEmail(code)
      const confirmed = result?.body?.confirmed

      setIsConfirmed(confirmed)

      if (confirmed) {
        await refreshUser()

        addNotification("email-verified", {
          type:  ALERT_TYPE_TEXT,
          props: {
            text:
              "Success! We've verified your email. Your email has been updated."
          }
        })
      } else {
        addNotification("email-verified", {
          type:  ALERT_TYPE_TEXT,
          color: "danger",
          props: {
            text: "Error! No confirmation code was provided or it has expired."
          }
        })
      }

      history.push(routes.accountSettings)
    },
    [history]
  )

  useEffect(() => {
    /* eslint-disable-next-line camelcase */
    confirmEmailAsync(verification_code as string)
  }, [])

  return (
    /* eslint-disable-next-line camelcase */
    <DocumentTitle title={`${site_name} | ${EMAIL_CONFIRM_PAGE_TITLE}`}>
      <div className="std-page-body container auth-page">
        <div className="row">
          <div className="col">
            {isPending && <p>Confirming...</p>}
            {isConfirmed && <p>Confirmed!</p>}
            {isFinished && !isConfirmed && (
              <React.Fragment>
                <p>No confirmation code was provided or it has expired.</p>
                <Link to={routes.accountSettings}>
                  Click Account Settings
                </Link>{" "}
                to change the email again.
              </React.Fragment>
            )}
          </div>
        </div>
      </div>
    </DocumentTitle>
  )
}
