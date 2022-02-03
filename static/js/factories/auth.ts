import casual from "casual-browserify"
import { FLOW_LOGIN, FLOW_REGISTER } from "../lib/auth"
import { AuthFlow, AuthResponse, AuthStates } from "../types/auth"

export const makeAuthResponse = (
  values: Partial<Omit<AuthResponse, "state" | "flow">> & {
    state: AuthStates
    flow: AuthFlow
  }
): AuthResponse => ({
  errors:        [],
  field_errors:  {},
  partial_token: casual.uuid,
  redirect_url:  undefined,
  extra_data:    {},
  ...values
})
export const makeLoginAuthResponse = (
  values: Partial<Omit<AuthResponse, "state">> & {
    state: AuthStates
  }
): AuthResponse =>
  makeAuthResponse({
    flow: FLOW_LOGIN,
    ...values
  })
export const makeRegisterAuthResponse = (
  values: Partial<Omit<AuthResponse, "state">> & {
    state: AuthStates
  }
): AuthResponse =>
  makeAuthResponse({
    flow: FLOW_REGISTER,
    ...values
  })
