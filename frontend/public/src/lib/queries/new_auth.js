// @flow
import { nthArg } from "ramda"

import { FLOW_REGISTER } from "../auth"

import type {
  AuthResponse,
  LegalAddress,
  UserProfile
} from "../../flow/authTypes"

// uses the next piece of state which is the second argument
const nextState = nthArg(1)

const DEFAULT_OPTIONS = {
  update:     {},
  options:    {
    method: "POST"
  }
}

export default {
  registerDetailsMutation: (
    name: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: ?UserProfile,
  ) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/profile/details/",
    body: {
      name,
      username,
      legal_address: legalAddress,
      user_profile:  userProfile,
    }
  }),

  registerAdditionalDetailsMutation: (
    name: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: ?UserProfile,
    next: ?string
  ) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/profile/extra/",
    body: {
      name,
      username,
      legal_address: legalAddress,
      user_profile:  userProfile,
      next
    }
  })
}
