import React from "react"
import moment from "moment"
import { range, reverse } from "ramda"
import { ErrorMessage, Field } from "formik"
import * as yup from "yup"

import {
  EMPLOYMENT_EXPERIENCE,
  EMPLOYMENT_FUNCTION,
  EMPLOYMENT_INDUSTRY,
  EMPLOYMENT_LEVEL,
  EMPLOYMENT_SIZE,
  HIGHEST_EDUCATION_CHOICES
} from "../../constants"
import FormError from "./elements/FormError"
import {
  newPasswordFieldValidation,
  usernameFieldValidation
} from "../../lib/validation"

export const NAME_REGEX = /^(?![~!@&)(+:'.?/,`-]+)([^/^$#*=[\]`%_;<>{}"|]+)$/

const seedYear = moment().year()

// Field Error messages
export const NAME_REGEX_FAIL_MESSAGE =
  "Name cannot start with a special character (~!@&)(+:'.?/,`-), and cannot contain any of (/^$#*=[]`%_;<>{}|\")"

export const legalAddressValidation = yup.object().shape({
  name: yup
    .string()
    .label("Full Name")
    .trim()
    .required()
    .min(2),
  legal_address: yup.object().shape({
    first_name: yup
      .string()
      .label("First Name")
      .trim()
      .matches(NAME_REGEX, NAME_REGEX_FAIL_MESSAGE)
      .required(),
    last_name: yup
      .string()
      .label("Last Name")
      .trim()
      .matches(NAME_REGEX, NAME_REGEX_FAIL_MESSAGE)
      .required(),
    country: yup
      .string()
      .label("Country")
      .length(2)
      .required()
  })
})

export const newAccountValidation = yup.object().shape({
  password: newPasswordFieldValidation,
  username: usernameFieldValidation
})

export const profileValidation = yup.object().shape({
  profile: yup.object().shape({
    gender: yup
      .string()
      .label("Gender")
      .nullable(),
    birth_year: yup
      .string()
      .label("Birth Year")
      .required(),
  })
})

type LegalAddressProps = {
  countries: Array<Country>,
  setFieldValue: Function,
  setFieldTouched: Function,
  values: Object,
  isNewAccount: boolean
}

const findStates = (country: string, countries: Array<Country>) => {
  if (!countries) {
    return null
  }

  const foundCountry = countries.find((elem) => elem.code === country)
  return foundCountry && foundCountry.states && foundCountry.states.length > 0 ? foundCountry.states : null
}

export const LegalAddressFields = ({
  countries,
  isNewAccount,
  values,
}: LegalAddressProps) => (
  <React.Fragment>
    <div className="form-group">
      <label htmlFor="legal_address.first_name" className="row">
        <div className="col-auto font-weight-bold">
          First Name<span className="required">*</span>
        </div>
        <div className="col-auto subtitle">Name that will appear on emails</div>
      </label>
      <Field
        type="text"
        name="legal_address.first_name"
        id="legal_address.first_name"
        className="form-control"
        autoComplete="given-name"
        aria-describedby="legal_address.first_name_error"
      />
      <ErrorMessage
        name="legal_address.first_name"
        id="legal_address.first_name_error"
        component={FormError}
      />
    </div>
    <div className="form-group">
      <label htmlFor="legal_address.last_name" className="font-weight-bold">
        Last Name<span className="required">*</span>
      </label>
      <Field
        type="text"
        name="legal_address.last_name"
        id="legal_address.last_name"
        className="form-control"
        autoComplete="family-name"
        aria-describedby="legal_address.last_name_error"
      />
      <ErrorMessage
        name="legal_address.last_name"
        id="legal_address.last_name_error"
        component={FormError}
      />
    </div>
    <div className="form-group">
      <label htmlFor="name" className="row">
        <div className="col-auto font-weight-bold">
          Full Name<span className="required">*</span>
        </div>
        <div className="col-auto subtitle">
          Name that will appear on your certificate
        </div>
      </label>
      <Field
        type="text"
        name="name"
        id="name"
        className="form-control"
        autoComplete="name"
        aria-describedby="nameError"
      />
      <ErrorMessage name="name" id="nameError" component={FormError} />
    </div>
    {isNewAccount ? (
      <React.Fragment>
        <div className="form-group">
          <label htmlFor="username" className="row">
            <div className="col-auto font-weight-bold">
              Public Username<span className="required">*</span>
            </div>
            <div className="col-auto subtitle">
              Name that will identify you in courses
            </div>
          </label>
          <Field
            type="text"
            name="username"
            className="form-control"
            autoComplete="username"
            id="username"
            aria-describedby="usernameError"
          />
          <ErrorMessage
            name="username"
            id="usernameError"
            component={FormError}
          />
        </div>
        <div className="form-group">
          <label htmlFor="password" className="font-weight-bold">
            Password<span className="required">*</span>
          </label>
          <Field
            type="password"
            name="password"
            id="password"
            aria-describedby="passwordError"
            className="form-control"
          />
          <ErrorMessage
            name="password"
            id="passwordError"
            component={FormError}
          />
          <div className="label-secondary">
            Passwords must contain at least 8 characters and at least 1 number
            and 1 letter.
          </div>
        </div>
      </React.Fragment>
    ) : null}
    <div className="form-group">
      <label htmlFor="legal_address.country" className="font-weight-bold">
        Country<span className="required">*</span>
      </label>
      <Field
        component="select"
        name="legal_address.country"
        id="legal_address.country"
        className="form-control"
        autoComplete="country"
        aria-describedby="legal_address.country_error"
      >
        <option value="">-----</option>
        {countries
          ? countries.map((country, i) => (
            <option key={i} value={country.code}>
              {country.name}
            </option>
          ))
          : null}
      </Field>

      <ErrorMessage
        name="legal_address.country"
        id="legal_address.country_error"
        component={FormError}
      />
    </div>
    {findStates(values.legal_address.country, countries) ? (<div className="form-group">
      <label htmlFor="legal_address.state" className="font-weight-bold">
        State<span className="required">*</span>
      </label>
      <Field
        component="select"
        name="legal_address.state"
        id="legal_address.state"
        className="form-control"
        autoComplete="state"
        aria-describedby="legal_address.state_error"
      >
        <option value="">-----</option>
        {findStates(values.legal_address.country, countries)
          ? findStates(values.legal_address.country, countries).map((state, i) => (
            <option key={i} value={state.code}>
              {state.name}
            </option>
          ))
          : null}
      </Field>
      <ErrorMessage
        name="legal_address.state"
        id="legal_address.state_error"
        component={FormError}
      />
    </div>) : null}
  </React.Fragment>
)

export const ProfileFields = () => (
  <React.Fragment>
    <div className="form-group">
      <div className="row">
        <div className="col">
          <label htmlFor="user_profile.gender" className="font-weight-bold">
            Gender
          </label>

          <Field
            component="select"
            name="user_profile.gender"
            id="user_profile.gender"
            className="form-control"
            aria-describedby="user_profile.genderError"
          >
            <option value="">-----</option>
            <option value="f">Female</option>
            <option value="m">Male</option>
            <option value="o">Other / Prefer not to say</option>
          </Field>
          <ErrorMessage
            name="user_profile.gender"
            id="user_profile.genderError"
            component={FormError}
          />
        </div>
        <div className="col">
          <label htmlFor="user_profile.year_of_birth" className="font-weight-bold">
            Year of Birth<span className="required">*</span>
          </label>
          <Field
            component="select"
            name="user_profile.year_of_birth"
            id="user_profile.year_of_birth"
            className="form-control"
            aria-describedby="user_profile.year_of_birth_error"
          >
            <option value="">-----</option>
            {reverse(range(seedYear - 120, seedYear - 14)).map((year, i) => (
              <option key={i} value={year}>
                {year}
              </option>
            ))}
          </Field>
          <ErrorMessage
            name="user_profile.year_of_birth"
            id="user_profile.year_of_birth_error"
            component={FormError}
          />
        </div>
      </div>
    </div>
  </React.Fragment>
)

export const AddlProfileFields = () => (
  <React.Fragment>
    <div className="form-group">
      <label htmlFor="profile.company" className="font-weight-bold">
        Company*
      </label>
      <Field
        type="text"
        name="profile.company"
        id="profile.company"
        aria-describedby="profile.companyError"
        className="form-control"
      />
      <ErrorMessage
        name="profile.company"
        id="profile.companyError"
        component={FormError}
      />
    </div>
    <div className="form-group">
      <label htmlFor="profile.job_title" className="font-weight-bold">
        Job Title*
      </label>
      <Field
        type="text"
        name="profile.job_title"
        id="profile.job_title"
        aria-describedby="profile.job_title_error"
        className="form-control"
      />
      <ErrorMessage
        name="profile.job_title"
        id="profile.job_title_error"
        component={FormError}
      />
    </div>
    <div className="form-group dotted" />
    <div className="form-group">
      <label htmlFor="profile.industry" className="font-weight-bold">
        Industry
      </label>
      <Field
        component="select"
        name="profile.industry"
        id="profile.industry"
        className="form-control"
      >
        <option value="">-----</option>
        {EMPLOYMENT_INDUSTRY.map((industry, i) => (
          <option key={i} value={industry}>
            {industry}
          </option>
        ))}
      </Field>
    </div>
    <div className="form-group">
      <label htmlFor="profile.job_function" className="font-weight-bold">
        Job Function
      </label>
      <Field
        component="select"
        name="profile.job_function"
        id="profile.job_function"
        className="form-control"
      >
        <option value="">-----</option>
        {EMPLOYMENT_FUNCTION.map((jobFunction, i) => (
          <option key={i} value={jobFunction}>
            {jobFunction}
          </option>
        ))}
      </Field>
    </div>
    <div className="form-group">
      <label htmlFor="profile.company_size" className="font-weight-bold">
        Company Size
      </label>
      <Field
        component="select"
        name="profile.company_size"
        id="profile.company_size"
        className="form-control"
      >
        <option value="">-----</option>
        {EMPLOYMENT_SIZE.map(([value, label], i) => (
          <option key={i} value={value}>
            {label}
          </option>
        ))}
      </Field>
    </div>
    <div className="form-group">
      <div className="row">
        <div className="col">
          <label
            htmlFor="profile.years_experience"
            className="font-weight-bold"
          >
            Years of Work Experience
          </label>
          <Field
            component="select"
            name="profile.years_experience"
            id="profile.years_experience"
            className="form-control"
          >
            <option value="">-----</option>
            {EMPLOYMENT_EXPERIENCE.map(([value, label], i) => (
              <option key={i} value={value}>
                {label}
              </option>
            ))}
          </Field>
        </div>
        <div className="col">
          <label
            htmlFor="profile.leadership_level"
            className="font-weight-bold"
          >
            Leadership Level
          </label>
          <Field
            component="select"
            name="profile.leadership_level"
            id="profile.leadership_level"
            className="form-control"
          >
            <option value="">-----</option>
            {EMPLOYMENT_LEVEL.map((level, i) => (
              <option key={i} value={level}>
                {level}
              </option>
            ))}
          </Field>
        </div>
      </div>
    </div>
    <div className="form-group">
      <div className="row">
        <div className="col">
          <label
            htmlFor="profile.highest_education"
            className="font-weight-bold"
          >
            Highest Level of Education
          </label>
          <Field
            component="select"
            name="profile.highest_education"
            id="profile.highest_education"
            className="form-control"
          >
            <option value="">-----</option>
            {HIGHEST_EDUCATION_CHOICES.map((level, i) => (
              <option key={i} value={level}>
                {level}
              </option>
            ))}
          </Field>
        </div>
      </div>
    </div>
  </React.Fragment>
)