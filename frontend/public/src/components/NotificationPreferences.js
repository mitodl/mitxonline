// @flow
import React from "react"

import {
  NOTIFICATION_APP_LABELS,
  NOTIFICATION_TYPE_LABELS,
  NOTIFICATION_TYPE_DESCRIPTIONS,
  NOTIFICATION_EMAIL_CADENCES
} from "../constants"

export type PreferenceConfig = {
  web: boolean,
  push: boolean,
  email: boolean,
  email_cadence: string,
  info: string
}

export type PreferenceGroup = {
  enabled: boolean,
  // Keyed by notification type -> the channels that type locks, e.g.
  // { new_discussion_post: ["push"] }. Not a flat list.
  non_editable: { [string]: Array<string> },
  notification_types: { [string]: PreferenceConfig }
}

type RowProps = {
  notificationApp: string,
  notificationType: string,
  config: PreferenceConfig,
  nonEditable: Array<string>,
  showEmail: boolean,
  onChange: (
    notificationApp: string,
    notificationType: string,
    notificationChannel: string,
    payload: Object
  ) => void
}

const labelForApp = (app: string) => NOTIFICATION_APP_LABELS[app] || app

const labelForType = (type: string) => NOTIFICATION_TYPE_LABELS[type] || type

// Our own copy first, then whatever the API happened to send, so a type added
// upstream still gets a description instead of leaving an empty gap.
export const descriptionForType = (type: string, info: string) =>
  NOTIFICATION_TYPE_DESCRIPTIONS[type] || info || ""

// The API returns non_editable keyed by notification type. Older releases
// returned a flat list for the whole app, so tolerate both.
export const lockedChannelsFor = (group: Object, notificationType: string) => {
  const nonEditable = group.non_editable
  if (!nonEditable) {
    return []
  }
  if (Array.isArray(nonEditable)) {
    return nonEditable
  }
  return nonEditable[notificationType] || []
}

export const PreferenceRow = ({
  notificationApp,
  notificationType,
  config,
  nonEditable,
  showEmail,
  onChange
}: RowProps) => {
  const label = labelForType(notificationType)
  const description = descriptionForType(notificationType, config.info)
  const webLocked = nonEditable.includes("web")
  const emailLocked = nonEditable.includes("email")
  const webId = `web-${notificationApp}-${notificationType}`
  const emailId = `email-${notificationApp}-${notificationType}`
  const cadenceId = `cadence-${notificationApp}-${notificationType}`

  return (
    <div className="notification-preference-row">
      <div className="notification-preference-text">
        <span className="notification-preference-label">{label}</span>
        {description ? (
          <span className="notification-preference-description">
            {description}
          </span>
        ) : null}
      </div>

      <div className="notification-preference-controls">
        <div className="form-check notification-preference-check">
          <input
            className="form-check-input"
            type="checkbox"
            id={webId}
            checked={config.web}
            disabled={webLocked}
            onChange={() =>
              onChange(notificationApp, notificationType, "web", {
                value: !config.web
              })
            }
          />
          <label className="form-check-label" htmlFor={webId}>
            On site
          </label>
        </div>

        {showEmail ? (
          <React.Fragment>
            <div className="form-check notification-preference-check">
              <input
                className="form-check-input"
                type="checkbox"
                id={emailId}
                checked={config.email}
                disabled={emailLocked}
                onChange={() =>
                  onChange(notificationApp, notificationType, "email", {
                    value: !config.email
                  })
                }
              />
              <label className="form-check-label" htmlFor={emailId}>
                Email
              </label>
            </div>

            {/* The cadence only means something while email delivery is on, so
                it appears alongside the email toggle rather than sitting greyed
                out on every row. */}
            {config.email && !emailLocked ? (
              <div className="notification-preference-cadence">
                <select
                  className="form-select"
                  id={cadenceId}
                  aria-label={`Email frequency for ${label}`}
                  value={config.email_cadence}
                  onChange={(e: Object) =>
                    onChange(
                      notificationApp,
                      notificationType,
                      "email_cadence",
                      { email_cadence: e.target.value }
                    )
                  }
                >
                  {NOTIFICATION_EMAIL_CADENCES.map(cadence => (
                    <option key={cadence} value={cadence}>
                      {cadence}
                    </option>
                  ))}
                </select>
              </div>
            ) : null}
          </React.Fragment>
        ) : null}
      </div>
    </div>
  )
}

type Props = {
  preferences: { [string]: PreferenceGroup },
  showEmailPreferences: boolean,
  onChange: (
    notificationApp: string,
    notificationType: string,
    notificationChannel: string,
    payload: Object
  ) => void
}

const NotificationPreferences = ({
  preferences,
  showEmailPreferences,
  onChange
}: Props) => {
  const groups = Object.entries(preferences || {}).filter(
    // eslint-disable-next-line no-unused-vars
    ([app, group]) => group.enabled
  )

  if (groups.length === 0) {
    return (
      <section className="notification-preferences" id="notifications">
        <h2>Notifications</h2>
        <p className="notification-preferences-intro">
          You have no notification settings to manage yet.
        </p>
      </section>
    )
  }

  return (
    <section className="notification-preferences" id="notifications">
      <h2>Notifications</h2>
      <p className="notification-preferences-intro">
        Choose how you hear about activity in your courses.
      </p>

      {groups.map(([app, group]) => (
        <div className="notification-preference-group" key={app}>
          <h3 className="notification-preference-group-title">
            {labelForApp(app)}
          </h3>
          {Object.entries(group.notification_types).map(([type, config]) => (
            <PreferenceRow
              key={type}
              notificationApp={app}
              notificationType={type}
              config={config}
              nonEditable={lockedChannelsFor(group, type)}
              showEmail={showEmailPreferences}
              onChange={onChange}
            />
          ))}
        </div>
      ))}
    </section>
  )
}

export default NotificationPreferences
