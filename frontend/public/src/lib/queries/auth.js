// @flow
import { pathOr, nthArg } from "ramda"

import { FLOW_LOGIN, FLOW_REGISTER } from "../auth"
import { getCsrfOptions } from "./util"

import type {
  AuthResponse,
  LegalAddress,
  UserProfile
} from "../../flow/authTypes"
import type { updateEmailResponse } from "../../flow/authTypes"

export const authSelector = (state: any) => state.entities.auth

export const updateEmailSelector = pathOr(null, ["entities", "updateEmail"])

// uses the next piece of state which is the second argument
const nextState = nthArg(1)

const DEFAULT_OPTIONS = {
  transform: (auth: ?AuthResponse) => ({ auth }),
  update:    {
    auth: nextState
  },
  options: {
    method: "POST"
  }
}

export default {
  loginEmailMutation: (email: string, next: ?string) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/login/email/",
    body: { email, next, flow: FLOW_LOGIN }
  }),

  loginPasswordMutation: (password: string, partialToken: string) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/login/password/",
    body: { password, partial_token: partialToken, flow: FLOW_LOGIN }
  }),

  registerEmailMutation: (
    email: string,
    recaptcha: ?string,
    next: ?string
  ) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/register/email/",
    body: { email, recaptcha, next, flow: FLOW_REGISTER }
  }),

  registerConfirmEmailMutation: (qsParams: Object) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/register/confirm/",
    body: {
      flow: FLOW_REGISTER,
      ...qsParams
    }
  }),

  registerDetailsMutation: (
    name: string,
    password: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: ?UserProfile,
    partialToken: string
  ) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/register/details/",
    body: {
      name,
      password,
      username,
      legal_address: legalAddress,
      user_profile:  userProfile,
      flow:          FLOW_REGISTER,
      partial_token: partialToken
    }
  }),

  registerAdditionalDetailsMutation: (
    name: string,
    password: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: ?UserProfile,
    partialToken: string,
    next: ?string
  ) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/register/extra/",
    body: {
      name,
      password,
      username,
      legal_address: legalAddress,
      user_profile:  userProfile,
      flow:          FLOW_REGISTER,
      partial_token: partialToken,
      next
    }
  }),

  forgotPasswordMutation: (email: string) => ({
    url:     "/api/password_reset/",
    body:    { email },
    options: {
      ...getCsrfOptions(),
      method: "POST"
    }
  }),

  changePasswordMutation: (oldPassword: string, newPassword: string) => ({
    url:     "/api/set_password/",
    options: getCsrfOptions(),
    body:    {
      current_password: oldPassword,
      new_password:     newPassword
    }
  }),

  forgotPasswordConfirmMutation: (
    newPassword: string,
    reNewPassword: string,
    token: string,
    uid: string
  ) => ({
    url:  "/api/password_reset/confirm/",
    body: {
      new_password:    newPassword,
      re_new_password: reNewPassword,
      token,
      uid
    },
    options: {
      ...getCsrfOptions(),
      method: "POST"
    }
  }),

  changeEmailMutation: (newEmail: string, password: string) => ({
    url:     "/api/change-emails/",
    options: {
      ...getCsrfOptions(),
      method: "POST"
    },
    body: {
      new_email: newEmail,
      password:  password
    }
  }),

  confirmEmailMutation: (code: string) => ({
    queryKey:  "updateEmail",
    url:       `/api/change-emails/${code}/`,
    transform: (json: ?updateEmailResponse) => ({
      updateEmail: json
    }),
    update: {
      updateEmail: (prev: updateEmailResponse, next: updateEmailResponse) =>
        next
    },
    options: {
      ...getCsrfOptions(),
      method: "PATCH"
    },
    body: {
      confirmed: true
    }
  })
}
