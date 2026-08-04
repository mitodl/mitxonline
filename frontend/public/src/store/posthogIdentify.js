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
//
// Nothing here guards against identifying the same person twice, because
// posthog "will ignore the subsequent calls" when identify is called
// repeatedly with the same data within a page load:
// https://posthog.com/docs/getting-started/identify-users
//
// Signing out has to be handled here too. Signin and signout happen on the SSO
// server, so there is no client-side signout to hook; instead we reset whenever
// the browser turns out to be anonymous while posthog still thinks it is
// identified. Without that, identify latches $user_state to "identified" and a
// logged-out browser goes on attributing events to whoever logged in last.
// mit-learn's ConfiguredPostHogProvider does the same thing for the same reason.
const posthogIdentifyMiddleware = () => (next: Function) => (action: any) => {
  const result = next(action)

  if (
    SETTINGS.posthog_api_host &&
    action.type === actionTypes.REQUEST_SUCCESS &&
    action.url === CURRENT_USER_URL
  ) {
    const currentUser = action.entities && action.entities.currentUser

    // Both branches key off what the response affirmatively says, so a
    // response carrying no user at all is left alone rather than reset, and so
    // is an authenticated user who simply has no global id.
    if (currentUser && currentUser.is_anonymous) {
      if (posthog.get_property("$user_state") !== "anonymous") {
        posthog.reset()
      }
    } else if (currentUser && currentUser.global_id) {
      posthog.identify(currentUser.global_id, {
        environment: SETTINGS.environment,
        user_id:     currentUser.global_id
      })
    }
  }

  return result
}

export default posthogIdentifyMiddleware
