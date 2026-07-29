// @flow
/* global SETTINGS:false */
import posthog from "posthog-js"
import { actionTypes } from "redux-query"

import { CURRENT_USER_URL } from "../lib/queries/users"

// Identifies the user to PostHog as soon as /api/v0/users/current_user/
// succeeds, regardless of which component triggered the request. This
// posthog project is shared with other MIT applications, and xpro
// identifies people by its own integer user ids, so integer ids collide
// across applications. Users with no global id are left unidentified
// rather than identified by a colliding id.
const posthogIdentifyMiddleware = () => (next: Function) => (action: any) => {
  const result = next(action)

  if (
    SETTINGS.posthog_api_host &&
    action.type === actionTypes.REQUEST_SUCCESS &&
    action.url === CURRENT_USER_URL
  ) {
    const currentUser = action.entities && action.entities.currentUser

    if (currentUser && currentUser.global_id) {
      posthog.identify(currentUser.global_id, {
        environment: SETTINGS.environment,
        user_id:     currentUser.id
      })
    }
  }

  return result
}

export default posthogIdentifyMiddleware
