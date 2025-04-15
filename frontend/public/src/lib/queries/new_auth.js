// @flow
import { nthArg } from "ramda"

import { FLOW_REGISTER } from "../auth"

import type {
  AuthResponse,
  LegalAddress,
  UserProfile
} from "../../flow/authTypes"

export const authSelector = (state: any) => state.entities.auth

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

  registerDetailsMutation: (
    name: string,
    password: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: ?UserProfile,
    partialToken: string
  ) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/profile/details",
    body: {
      name,
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
    url:  "/api/profile/extra/",
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
}
