// @flow

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

export type AuthFieldErrors = {
  [string]: string
}

export type AuthExtraData = {
  name?: string
}

export type AuthResponse = {
  partial_token: ?string,
  flow: AuthFlow,
  state: AuthStates,
  errors: AuthErrors,
  field_errors: AuthFieldErrors,
  redirect_url: ?string,
  extra_data: AuthExtraData
}

export type LegalAddress = {
  first_name: string,
  last_name: string,
  country: string,
  street_address?: Array<string>,
  state?: string,
  postal_code?: string,
  company?: string
}

export type ExtendedLegalAddress = LegalAddress & {
  city: string,
  email: string
}

export type UnusedCoupon = {
  coupon_code: string,
  product_id: number,
  expiration_date: string
}

export type UserProfile = {
  gender: ?string,
  year_of_birth: number,
  company: ?string,
  industry: ?string,
  job_title: ?string,
  job_function: ?string,
  years_experience: ?number,
  company_size: ?number,
  leadership_level: ?string,
  highest_education: ?string,
  addl_field_flag: boolean,
  type_is_student: ?boolean,
  type_is_professional: ?boolean,
  type_is_educator: ?boolean,
  type_is_other: ?boolean,
}

export type User = {
  id: number,
  username: string,
  email: string,
  name: string,
  created_on: string,
  updated_on: string,
  legal_address: ?LegalAddress,
  user_profile: ?UserProfile,
}

export type AnonymousUser = {
  is_anonymous: true,
  is_authenticated: false
}

export type LoggedInUser = {
  is_anonymous: false,
  is_authenticated: true,
  is_editor: boolean
} & User

export type CurrentUser = AnonymousUser | LoggedInUser

export type StateOrTerritory = {
  name: string,
  code: string
}

export type Country = {
  name: string,
  code: string,
  states: Array<StateOrTerritory>
}

export type ProfileForm = {
  profile: UserProfile
}

export type EmailFormValues = {
  email: string
}

export type PasswordFormValues = {
  password: string
}

export type UserProfileForm = {
  email: string,
  name: string,
  legal_address: ?LegalAddress
}

export type updateEmailResponse = {
  confirmed: boolean,
  detail: ?string
}

export type LearnerRecordUser = {
  name: string,
  email: string,
  username: string,
}
