/* eslint-disable @typescript-eslint/no-unused-vars */
/* eslint-disable camelcase */

interface Settings {
  reactGaDebug: string
  gaTrackingID: string
  public_path: string
  environment: string
  release_version: string
  sentry_dsn: string
  support_email: string
  site_name: string
  recaptchaKey: string | null
  user: {
    username: string
    email: string
    name: string
  } | null
}
