/* eslint camelcase: "off" */
// API response types
export type AuthStates =
  | "success"
  | "inactive"
  | "invalid-email"
  | "user-blocked"
  | "error"
  | "error-temporary"
  | "login/email"
  | "login/password"
  | "login/provider"
  | "register/email"
  | "register/confirm-sent"
  | "register/confirm"
  | "register/details"
  | "register/required"
export type AuthFlow = "register" | "login"
export type AuthErrors = Array<string>
export type AuthFieldErrors = Record<string, string>
export type AuthExtraData = {
  name?: string
}
export type AuthResponse = {
  partial_token: string | null | undefined
  flow: AuthFlow
  state: AuthStates
  errors: AuthErrors
  field_errors: AuthFieldErrors
  redirect_url: string | null | undefined
  extra_data: AuthExtraData
}
export type LegalAddress = {
  first_name: string
  last_name: string
  country: string
  street_address?: Array<string>
  city?: string
  state_or_territory?: string
  postal_code?: string
  company?: string
}
export type ExtendedLegalAddress = LegalAddress & {
  city: string
  email: string
}
export type UnusedCoupon = {
  coupon_code: string
  product_id: number
  expiration_date: string
}
export type Profile = {
  gender: string
  birth_year: number
  company: string
  industry: string | null | undefined
  job_title: string
  job_function: string | null | undefined
  years_experience: number | null | undefined
  company_size: number | null | undefined
  leadership_level: string | null | undefined
  highest_education: string | null | undefined
}

export type AnonymousUser = {
  is_anonymous: true
  is_authenticated: false
}
export type LoggedInUser = {
  is_anonymous: false
  is_authenticated: true

  // The rest of these are unique to a logged in user
  id: number
  username: string
  email: string
  name: string
  created_on: string
  updated_on: string
  legal_address: LegalAddress | null | undefined
  is_editor: boolean
}
export type CurrentUser = AnonymousUser | LoggedInUser

export type StateOrTerritory = {
  name: string
  code: string
}
export type Country = {
  name: string
  code: string
  states: Array<StateOrTerritory>
}
export type ProfileForm = {
  profile: Profile
}
export type EmailFormValues = {
  email: string
}
export type PasswordFormValues = {
  password: string
}
export type CreateUserProfileForm = {
  name: string
  password: string
  username: string
  legal_address: LegalAddress
}

export type EditUserProfileForm = {
  email: string
  name: string
  password: string
  legal_address: LegalAddress | null | undefined
}
export type updateEmailResponse = {
  confirmed: boolean
  detail: string | null | undefined
}
