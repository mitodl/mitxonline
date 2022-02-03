import { pathOr } from "ramda"
import { QueryConfig } from "redux-query"
import {
  AuthResponse,
  LegalAddress,
  updateEmailResponse
} from "../../types/auth"
import { FLOW_LOGIN, FLOW_REGISTER } from "../auth"
import { getCsrfOptions, nextState } from "./util"

export const authSelector = (state: any) => state.entities.auth
export const updateEmailSelector = pathOr(null, ["entities", "updateEmail"])

const DEFAULT_OPTIONS = {
  transform: (auth: AuthResponse) => ({
    auth
  }),
  update: {
    auth: nextState
  },
  options: {
    method: "POST"
  }
}

export function loginEmailMutation(
  email: string,
  next: string | null | undefined
): QueryConfig {
  return {
    ...DEFAULT_OPTIONS,
    url:  "/api/login/email/",
    body: {
      email,
      next,
      flow: FLOW_LOGIN
    }
  }
}

export function loginPasswordMutation(
  password: string,
  partialToken: string
): QueryConfig {
  return {
    ...DEFAULT_OPTIONS,
    url:  "/api/login/password/",
    body: {
      password,
      partial_token: partialToken,
      flow:          FLOW_LOGIN
    }
  }
}

export function registerEmailMutation(
  email: string,
  recaptcha: string | null | undefined,
  next: string | null | undefined
): QueryConfig {
  return {
    ...DEFAULT_OPTIONS,
    url:  "/api/register/email/",
    body: {
      email,
      recaptcha,
      next,
      flow: FLOW_REGISTER
    }
  }
}

export function registerConfirmEmailMutation(
  qsParams: Record<string, any>
): QueryConfig {
  return {
    ...DEFAULT_OPTIONS,
    url:  "/api/register/confirm/",
    body: {
      flow: FLOW_REGISTER,
      ...qsParams
    }
  }
}

export function registerDetailsMutation(
  name: string,
  password: string,
  username: string,
  legalAddress: LegalAddress,
  partialToken: string
): QueryConfig {
  return {
    ...DEFAULT_OPTIONS,
    url:  "/api/register/details/",
    body: {
      name,
      password,
      username,
      legal_address: legalAddress,
      flow:          FLOW_REGISTER,
      partial_token: partialToken
    }
  }
}

export function forgotPasswordMutation(email: string): QueryConfig {
  return {
    url:  "/api/password_reset/",
    body: {
      email
    },
    options: { ...getCsrfOptions(), method: "POST" }
  }
}

export function changePasswordMutation(
  oldPassword: string,
  newPassword: string
): QueryConfig {
  return {
    url:     "/api/set_password/",
    options: getCsrfOptions(),
    body:    {
      current_password: oldPassword,
      new_password:     newPassword
    }
  }
}

export function forgotPasswordConfirmMutation(
  newPassword: string,
  reNewPassword: string,
  token: string,
  uid: string
): QueryConfig {
  return {
    url:  "/api/password_reset/confirm/",
    body: {
      new_password:    newPassword,
      re_new_password: reNewPassword,
      token,
      uid
    },
    options: { ...getCsrfOptions(), method: "POST" }
  }
}

export function changeEmailMutation(
  newEmail: string,
  password: string
): QueryConfig {
  return {
    url:     "/api/change-emails/",
    options: { ...getCsrfOptions(), method: "POST" },
    body:    {
      new_email: newEmail,
      password:  password
    }
  }
}

export function confirmEmailMutation(code: string): QueryConfig {
  return {
    queryKey:  "updateEmail",
    url:       `/api/change-emails/${code}/`,
    transform: (json: updateEmailResponse) => ({
      updateEmail: json
    }),
    update: {
      updateEmail: (_: updateEmailResponse, next: updateEmailResponse) => next
    },
    options: { ...getCsrfOptions(), method: "PATCH" },
    body:    {
      confirmed: true
    }
  }
}
