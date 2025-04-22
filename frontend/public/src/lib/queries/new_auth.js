// @flow

import type { LegalAddress, UserProfile } from "../../flow/authTypes"
import { getCsrfOptions } from "./util"

// uses the next piece of state which is the second argument

const DEFAULT_OPTIONS = {
  update:  {},
  options: {
    ...getCsrfOptions(),
    method: "POST"
  }
}

export default {
  registerDetailsMutation: (
    name: string,
    username: string,
    legalAddress: LegalAddress,
    userProfile: ?UserProfile
  ) => ({
    ...DEFAULT_OPTIONS,
    url:  "/api/profile/details/",
    body: {
      name,
      username,
      legal_address: legalAddress,
      user_profile:  userProfile
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
