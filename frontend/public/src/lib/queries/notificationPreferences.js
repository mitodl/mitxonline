// @flow
import { pathOr } from "ramda"

import { getCsrfOptions, nextState } from "./util"

export const notificationPreferencesSelector = pathOr(null, [
  "entities",
  "notificationPreferences"
])

export const NOTIFICATION_PREFERENCES_URL = "/api/notification-preferences/"

export default {
  notificationPreferencesQuery: () => ({
    queryKey:  "notificationPreferences",
    url:       NOTIFICATION_PREFERENCES_URL,
    transform: (json: Object) => ({ notificationPreferences: json }),
    update:    {
      notificationPreferences: nextState
    },
    force: true
  }),

  // Open edX updates a single channel per request, so each toggle or cadence
  // change is its own mutation. The queryKey includes the target so concurrent
  // changes to different rows don't clobber each other's query state.
  updateNotificationPreferenceMutation: (
    notificationApp: string,
    notificationType: string,
    notificationChannel: string,
    payload: Object
  ) => ({
    queryKey: `updateNotificationPreference-${notificationApp}-${notificationType}-${notificationChannel}`,
    url:      NOTIFICATION_PREFERENCES_URL,
    options:  {
      ...getCsrfOptions(),
      method: "PUT"
    },
    body: {
      notification_app:     notificationApp,
      notification_type:    notificationType,
      notification_channel: notificationChannel,
      ...payload
    }
  })
}
