// @flow
import { nthArg, objOf, pathOr } from "ramda"

import { getCsrfOptions } from "./util"

import type {
  CurrentUser,
  Country,
  UserProfileForm
} from "../../flow/authTypes"

export const currentUserSelector = (state: any): ?CurrentUser =>
  state.entities.currentUser

// replace the previous state with the next state without merging
const nextState = nthArg(1)

// project the result into entities.currentUser
const transformCurrentUser = objOf("currentUser")

const updateResult = {
  currentUser: nextState
}

const DEFAULT_OPTIONS = {
  options: {
    ...getCsrfOptions(),
    method: "PATCH"
  }
}

export default {
  currentUserQuery: () => ({
    url:       "/api/users/me",
    transform: transformCurrentUser,
    update:    updateResult
  }),
  countriesSelector: pathOr(null, ["entities", "countries"]),
  countriesQuery:    () => ({
    queryKey:  "countries",
    url:       "/api/countries/",
    transform: objOf("countries"),
    update:    {
      countries: (prev: Array<Country>, next: Array<Country>) => next
    }
  }),
  editProfileMutation: (profileData: UserProfileForm) => ({
    ...DEFAULT_OPTIONS,
    transform: transformCurrentUser,
    update:    updateResult,
    url:       "/api/users/me",
    body:      {
      ...profileData
    }
  })
}
