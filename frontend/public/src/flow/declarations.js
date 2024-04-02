// @flow
/* eslint-disable no-unused-vars */

declare type Settings = {
  public_path: string,
  reactGaDebug: string,
  sentry_dsn: string,
  release_version: string,
  environment: string,
  gtmTrackingID: ?string,
  gaTrackingID: ?string,
  recaptchaKey: ?string,
  support_email: string,
  features: {
  },
  site_name: string,
  zendesk_config: {
    help_widget_enabled: boolean,
    help_widget_key: ?string
  },
  digital_credentials: boolean,
  digital_credentials_supported_runs: Array<string>,
  posthog_api_token: ?string,
  posthog_api_host: ?string,
  posthog_feature_flag_request_timeout_ms: ?string,
}
declare var SETTINGS: Settings

// mocha
declare var it: Function
declare var beforeEach: Function
declare var afterEach: Function
declare var describe: Function

declare var module: {
  hot: any
}
