// @flow
import { include } from "named-urls"
import qs from "query-string"

export const getNextParam = (search: string) => qs.parse(search).next || "/"

export const routes = {
  root:                   "/",
  dashboard:              "/dashboard/",
  profile:                "/profile/",
  create_profile:         "/create-profile/",
  create_profile_extra:   "/create-profile-extra/",
  accountSettings:        "/account-settings/",
  logout:                 "/logout/",
  orderHistory:           "/orders/history",
  catalogTabByDepartment: "/catalog/:tab/:department",
  catalogTab:             "/catalog/:tab",
  catalog:                "/catalog/",
  apiGatewayLogin:        "/login/",

  // authentication related routes
  login: include("/signin/", {
    begin:    "",
    email:    "email/",
    password: "password/", // pragma: allowlist secret
    forgot:   include("forgot-password/", {
      begin:   "",
      confirm: "confirm/:uid/:token/"
    })
  }),

  register: include("/create-account/", {
    begin:             "",
    confirm:           "confirm/",
    confirmSent:       "confirm-sent/",
    details:           "details/",
    additionalDetails: "additional-details/",
    error:             "error/",
    denied:            "denied/"
  }),

  account: include("/account/", {
    confirmEmail: "confirm-email",
    action:       include("action/start/", {
      updateEmail:    "update-email/",
      updatePassword: "update-password/"
    })
  }),

  cart: include("/cart/", {
    begin: ""
  }),

  orderReceipt: "/orders/receipt/:orderId",

  informationLinks: include("", {
    termsOfService: "terms-of-service",
    privacyPolicy:  "privacy-policy",
    honorCode:      "honor-code"
  }),

  learnerRecords:      "/records/:program/",
  sharedLearnerRecord: "/records/shared/:program/"
}
