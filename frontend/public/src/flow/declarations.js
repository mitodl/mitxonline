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
    enable_multiple_cart_items?: boolean
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
  unified_ecommerce_url: ?string,
  oidc_login_url: ?string,
  mit_learn_dashboard_url: ?string,
  api_gateway_enabled: boolean,
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
