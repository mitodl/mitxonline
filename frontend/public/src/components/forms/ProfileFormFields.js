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
  passwordField,
  usernameField,
  passwordFieldRegex,
  passwordFieldErrorMessage,
  usernameFieldRegex,
  usernameFieldErrorMessage
} from "../../lib/validation"

export const NAME_REGEX =
  "^(?![~!@&\\)\\(+:'.?,\\-]+)([^\\/\\^$#*=\\[\\]`%_;\\\\<>\\{\\}\"\\|]+)$"

const seedYear = moment().year()

// Field Error messages
export const NAME_REGEX_FAIL_MESSAGE =
  "Name cannot start with a special character (~!@&)(+:'.?,-), and cannot contain any of (/^$#*=[]`%_;\\<>{}\"|)"

export const fullNameRegex = "^.{2,255}$"
const fullNameErrorMessage = "Full name must be between 2 and 254 characters."

const countryRegex = "^\\S{2,}$"

export const legalAddressValidation = yup.object().shape({
  name:          yup.string().label("Full Name"),
  legal_address: yup.object().shape({
    first_name: yup.string().label("First Name"),
    last_name:  yup.string().label("Last Name"),
    country:    yup.string().label("Country"),
    state:      yup
      .string()
      .label("State")
      .when("country", {
        is:   value => value === "US" || value === "CA",
        then: yup
          .string()
          .required("State is a required field")
          .typeError("State is a required field"),
        otherwise: yup.string().nullable()
      })
  })
})

export const newAccountValidation = yup.object().shape({
  password: passwordField,
  username: usernameField
})

export const profileValidation = yup.object().shape({
  user_profile: yup.object().shape({
    gender: yup
      .string()
      .label("Gender")
      .nullable(),
    year_of_birth: yup
      .number()
      .min(13 - new Date().getFullYear())
      .label("Year of Birth")
      .required()
      .typeError("Year of Birth is a required field")
  })
})

export const addlProfileFieldsValidation = yup.object().shape({
  user_profile: yup.object().shape({
    company: yup
      .string()
      .label("Company")
      .nullable(),
    job_title: yup
      .string()
      .label("Job Title")
      .nullable(),
    industry: yup
      .string()
      .label("Industry")
      .nullable(),
    job_function: yup
      .string()
      .label("Job Function")
      .nullable(),
    company_size: yup
      .string()
      .label("Company Size")
      .nullable(),
    years_experience: yup
      .string()
      .label("Years of Work Experience")
      .nullable(),
    leadership_level: yup
      .string()
      .label("Leadership Level")
      .nullable()
  }),
  highest_education: yup
    .string()
    .label("Highest Level of Education")
    .nullable(),
  type_is_student:      yup.boolean().nullable(),
  type_is_professional: yup.boolean().nullable(),
  type_is_educator:     yup.boolean().nullable(),
  type_is_other:        yup.boolean().nullable()
})

export const requireLearnerTypeFields = {
  name:      "require_learner_type_fields",
  message:   "Please specify which category you fall into.",
  exclusive: false,
  params:    {},
  test:      (testValue: any, context: any) => {
    return (
      testValue ||
      context.parent.type_is_student ||
      context.parent.type_is_professional ||
      context.parent.type_is_educator ||
      context.parent.type_is_other
    )
  }
}

type LegalAddressProps = {
  countries: Array<Country>,
  setFieldValue: Function,
  setFieldTouched: Function,
  values: Object,
  isNewAccount: boolean
}

type AddlProfileFieldsProps = {
  values: Object,
  setFieldValue: Function,
  requireAddlFields: ?boolean
}

const findStates = (country: string, countries: Array<Country>) => {
  if (!countries) {
    return null
  }

  const foundCountry = countries.find(elem => elem.code === country)
  return foundCountry && foundCountry.states && foundCountry.states.length > 0
    ? foundCountry.states
    : null
}

const renderYearOfBirthField = () => {
  return (
    <div>
      <label htmlFor="user_profile.year_of_birth" className="fw-bold">
        Year of Birth<span className="required">*</span>
      </label>
      <Field
        component="select"
        name="user_profile.year_of_birth"
        id="user_profile.year_of_birth"
        className="form-control"
        autoComplete="bday-year"
        aria-describedby="user_profile.year_of_birth_error"
        required
      >
        <option value="">-----</option>
        {reverse(range(seedYear - 120, seedYear - 13)).map((year, i) => (
          <option key={i} value={year}>
            {year}
          </option>
        ))}
      </Field>
    </div>
  )
}

export const LegalAddressFields = ({
  countries,
  isNewAccount,
  values
}: LegalAddressProps) => (
  <React.Fragment>
    <div className="form-group">
      <label htmlFor="legal_address.first_name" className="label-helptext">
        <div className="fw-bold">
          First Name<span className="required">*</span>
        </div>
        <div id="first-name-subtitle" className="subtitle">
          Name that will appear on emails
        </div>
      </label>
      <Field
        type="text"
        name="legal_address.first_name"
        id="legal_address.first_name"
        className="form-control"
        autoComplete="given-name"
        aria-describedby="first-name-subtitle"
        aria-label="First Name"
        required
        pattern={NAME_REGEX}
        title={NAME_REGEX_FAIL_MESSAGE}
      />
    </div>
    <div className="form-group">
      <label htmlFor="legal_address.last_name" className="fw-bold">
        Last Name<span className="required">*</span>
      </label>
      <Field
        type="text"
        name="legal_address.last_name"
        id="legal_address.last_name"
        className="form-control"
        autoComplete="family-name"
        required
        pattern={NAME_REGEX}
        title={NAME_REGEX_FAIL_MESSAGE}
      />
    </div>
    <div className="form-group">
      <label htmlFor="name" className="label-helptext">
        <div className="fw-bold">
          Full Name<span className="required">*</span>
        </div>
        <div id="full-name-subtitle" className="subtitle">
          Name that will appear on your certificate
        </div>
      </label>
      <Field
        type="text"
        name="name"
        id="name"
        className="form-control"
        autoComplete="name"
        aria-describedby="full-name-subtitle"
        aria-label="Full Name"
        required
        pattern={fullNameRegex}
        title={fullNameErrorMessage}
      />
    </div>
    {isNewAccount ? (
      <React.Fragment>
        <div className="form-group">
          <label htmlFor="username" className="label-helptext">
            <div className="fw-bold">
              Public Username<span className="required">*</span>
            </div>
            <div id="username-subtitle" className="subtitle">
              Name that will identify you in courses
            </div>
          </label>
          <Field
            type="text"
            name="username"
            className="form-control"
            autoComplete="username"
            id="username"
            aria-describedby="username-subtitle"
            aria-label="Public Username"
            required
            pattern={usernameFieldRegex}
            title={usernameFieldErrorMessage}
          />
          <ErrorMessage name="username" component={FormError} />
        </div>
        <div className="form-group">
          <label htmlFor="password" className="fw-bold">
            Password<span className="required">*</span>
          </label>
          <Field
            type="password"
            name="password"
            id="password"
            aria-describedby="password-subtitle"
            className="form-control"
            autoComplete="new-password"
            required
            pattern={passwordFieldRegex}
            title={passwordFieldErrorMessage}
          />
          <div id="password-subtitle" className="label-secondary">
            Passwords must contain at least 8 characters and at least 1 number
            and 1 letter.
          </div>
        </div>
      </React.Fragment>
    ) : null}
    <div className="form-group">
      <label htmlFor="legal_address.country" className="fw-bold">
        Country<span className="required">*</span>
      </label>
      <Field
        component="select"
        name="legal_address.country"
        id="legal_address.country"
        className="form-control"
        autoComplete="country"
        required
        pattern={countryRegex}
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
    </div>
    {findStates(values.legal_address.country, countries) ? (
      <div className="form-group">
        <label htmlFor="legal_address.state" className="fw-bold">
          State<span className="required">*</span>
        </label>
        <Field
          component="select"
          name="legal_address.state"
          id="legal_address.state"
          className="form-control"
          autoComplete="state"
          required
        >
          <option value="">-----</option>
          {findStates(values.legal_address.country, countries)
            ? findStates(values.legal_address.country, countries).map(
              (state, i) => (
                <option key={i} value={state.code}>
                  {state.name}
                </option>
              )
            )
            : null}
        </Field>
      </div>
    ) : null}
    {isNewAccount ? (
      <div className="form-group">{renderYearOfBirthField()}</div>
    ) : null}
  </React.Fragment>
)

export const ProfileFields = () => (
  <React.Fragment>
    <div className="form-group">
      <div className="row">
        <div className="col">
          <label htmlFor="user_profile.gender" className="fw-bold">
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
            <option value="t">Transgender</option>
            <option value="nb">Non-binary/non-conforming</option>
            <option value="o">Other / Prefer not to say</option>
          </Field>
          <ErrorMessage
            name="user_profile.gender"
            id="user_profile.genderError"
            component={FormError}
          />
        </div>
        <div className="col">{renderYearOfBirthField()}</div>
      </div>
    </div>
  </React.Fragment>
)

export const AddlProfileFields = ({
  values,
  requireAddlFields
}: AddlProfileFieldsProps) => (
  <React.Fragment>
    <div className="form-group">
      <div className="row">
        <div className="col">
          <label htmlFor="user_profile.highest_education" className="fw-bold">
            Highest Level of Education
          </label>
          {requireAddlFields ? <span className="required">*</span> : ""}
          <Field
            component="select"
            name="user_profile.highest_education"
            id="user_profile.highest_education"
            className="form-control"
            required={requireAddlFields}
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
    <div className="form-group">
      <label id="occupation-label" className="fw-bold">
        Are you a{requireAddlFields ? <span className="required">*</span> : ""}
      </label>
      <div className="row">
        <div className="col-6">
          <div className="form-check">
            <Field
              type="checkbox"
              name="user_profile.type_is_student"
              id="user_profile.type_is_student"
              className="form-check-input"
              aria-labelledby="occupation-label student-label"
              defaultChecked={values.user_profile.type_is_student}
              required={false}
            />
            <label
              className="form-check-label"
              htmlFor="user_profile.type_is_student"
              id="student-label"
            >
              {" "}
              Student
            </label>
          </div>
          <div className="form-check">
            <Field
              type="checkbox"
              name="user_profile.type_is_professional"
              id="user_profile.type_is_professional"
              className="form-check-input"
              aria-labelledby="occupation-label professional-label"
              defaultChecked={values.user_profile.type_is_professional}
            />
            <label
              className="form-check-label"
              htmlFor="user_profile.type_is_professional"
              id="professional-label"
            >
              {" "}
              Professional
            </label>
          </div>
        </div>
        <div className="col-6">
          <div className="form-check">
            <Field
              type="checkbox"
              name="user_profile.type_is_educator"
              id="user_profile.type_is_educator"
              className="form-check-input"
              aria-labelledby="occupation-label educator-label"
              defaultChecked={values.user_profile.type_is_educator}
            />
            <label
              className="form-check-label"
              htmlFor="user_profile.type_is_educator"
              id="educator-label"
            >
              {" "}
              Educator
            </label>
          </div>
          <div className="form-check">
            <Field
              type="checkbox"
              name="user_profile.type_is_other"
              id="user_profile.type_is_other"
              className="form-check-input"
              aria-labelledby="occupation-label other-label"
              defaultChecked={values.user_profile.type_is_other}
            />
            <label
              className="form-check-label"
              htmlFor="user_profile.type_is_other"
              id="other-label"
            >
              {" "}
              Other
            </label>
          </div>
        </div>
      </div>
      <div className="row">
        <div className="col-12">
          <ErrorMessage
            name="user_profile.type_is_student"
            id="user_profile.type_is_student_Error"
            component={FormError}
          />
        </div>
      </div>
    </div>
    {values.user_profile.type_is_professional ? (
      <React.Fragment>
        <Field
          type="hidden"
          name="user_profile.addl_fields_flag"
          value={true}
        />
        <div className="form-group">
          <label htmlFor="user_profile.company" className="fw-bold">
            Company
          </label>
          <Field
            type="text"
            name="user_profile.company"
            id="user_profile.company"
            autoComplete="organization"
            aria-describedby="user_profile.companyError"
            className="form-control"
          />
          <ErrorMessage
            name="user_profile.company"
            id="user_profile.companyError"
            component={FormError}
          />
        </div>
        <div className="row">
          <div className="col">
            <div className="form-group">
              <label htmlFor="user_profile.job_title" className="fw-bold">
                Job Title
              </label>
              <Field
                type="text"
                name="user_profile.job_title"
                id="user_profile.job_title"
                autoComplete="organization-title"
                aria-describedby="user_profile.job_title_error"
                className="form-control"
              />
              <ErrorMessage
                name="user_profile.job_title"
                id="user_profile.job_title_error"
                component={FormError}
              />
            </div>
          </div>
          <div className="col">
            <div className="form-group">
              <label htmlFor="user_profile.company_size" className="fw-bold">
                Company Size
              </label>
              <Field
                component="select"
                name="user_profile.company_size"
                id="user_profile.company_size"
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
          </div>
        </div>
        <div className="row">
          <div className="col">
            <div className="form-group">
              <label htmlFor="user_profile.industry" className="fw-bold">
                Industry
              </label>
              <Field
                component="select"
                name="user_profile.industry"
                id="user_profile.industry"
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
          </div>
          <div className="col">
            <div className="form-group">
              <label htmlFor="user_profile.job_function" className="fw-bold">
                Job Function
              </label>
              <Field
                component="select"
                name="user_profile.job_function"
                id="user_profile.job_function"
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
          </div>
        </div>
        <div className="row">
          <div className="col">
            <div className="form-group">
              <label
                htmlFor="user_profile.years_experience"
                className="fw-bold"
              >
                Years of Work Experience
              </label>
              <Field
                component="select"
                name="user_profile.years_experience"
                id="user_profile.years_experience"
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
          </div>
          <div className="col">
            <div className="form-group">
              <label
                htmlFor="user_profile.leadership_level"
                className="fw-bold"
              >
                Leadership Level
              </label>
              <Field
                component="select"
                name="user_profile.leadership_level"
                id="user_profile.leadership_level"
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
      </React.Fragment>
    ) : null}
  </React.Fragment>
)
