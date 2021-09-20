// @flow
import { include } from "named-urls"
import qs from "query-string"

export const getNextParam = (search: string) => qs.parse(search).next || "/"

export const routes = {
  root:            "/",
  dashboard:       "/dashboard/",
  accountSettings: "/account-settings/",
  logout:          "/logout/",

  // authentication related routes
  login: include("/signin/", {
    begin:    "",
    password: "password/",
    forgot:   include("forgot-password/", {
      begin:   "",
      confirm: "confirm/:uid/:token/"
    })
  }),

  register: include("/create-account/", {
    begin:       "",
    confirm:     "confirm/",
    confirmSent: "confirm-sent/",
    details:     "details/",
    error:       "error/",
    denied:      "denied/"
  }),

  profile: include("/profile/", {
    view:   "",
    update: "edit/"
  }),

  account: include("/account/", {
    confirmEmail: "confirm-email"
  }),

  informationLinks: include("", {
    termsOfService: "terms-of-service",
    privacyPolicy:  "privacy-policy"
  })
}
