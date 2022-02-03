import { objOf, pathOr } from "ramda"
import { QueryConfig } from "redux-query"
import { Country, CurrentUser, EditUserProfileForm } from "../../types/auth"
import { getCsrfOptions, nextState } from "./util"

// project the result into entities.currentUser
const transformCurrentUser = objOf("currentUser")
const updateResult = {
  currentUser: nextState
}
const DEFAULT_OPTIONS = {
  options: { ...getCsrfOptions(), method: "PATCH" }
}

export function currentUserSelector(state: any): CurrentUser | null {
  return state.entities.currentUser ?? null
}

export function currentUserQuery(): QueryConfig {
  return {
    url:       "/api/users/me",
    transform: transformCurrentUser,
    update:    updateResult,
    options:   {
      method: "GET"
    }
  }
}
export const countriesSelector = pathOr([], ["entities", "countries"])

export function countriesQuery(): QueryConfig {
  return {
    queryKey:  "countries",
    url:       "/api/countries/",
    transform: objOf("countries"),
    update:    {
      countries: (_: Array<Country>, next: Array<Country>) => next
    }
  }
}

export function editProfileMutation(
  profileData: EditUserProfileForm
): QueryConfig {
  return {
    ...DEFAULT_OPTIONS,
    transform: transformCurrentUser,
    update:    updateResult,
    url:       "/api/users/me",
    body:      { ...profileData }
  }
}
