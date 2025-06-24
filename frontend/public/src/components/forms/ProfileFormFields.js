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
import CardLabel from "../input/CardLabel"

import {
  newPasswordField,
  usernameField,
  passwordFieldErrorMessage
} from "../../lib/validation"

export const NAME_REGEX =
  /^(?![~!@&)(+:'.?,-])(?!.*[(/^$#*=[\]`%_;\\<>{}"|)]).*$/

const seedYear = moment().year()

// Field Error messages
export const NAME_REGEX_FAIL_MESSAGE =
  "Name cannot start with a special character (~!@&)(+:'.?,-), and cannot contain any of (/^$#*=[]`%_;\\<>{}\"|)"

export const legalAddressValidation = yup.object().shape({
  name:          yup.string().required().label("Full Name").min(2).max(254),
  legal_address: yup.object().shape({
    first_name: yup
      .string()
      .required()
      .label("First Name")
      .matches(NAME_REGEX, NAME_REGEX_FAIL_MESSAGE),
    last_name: yup
      .string()
      .required()
      .label("Last Name")
      .matches(NAME_REGEX, NAME_REGEX_FAIL_MESSAGE),
    country: yup
      .string()
      .required()
      .label("Country")
      .matches(/^[A-Z]+$/, "Country code must be uppercase letters only")
      .min(2, "Country code must be exactly 2 letters")
      .max(2, "Country code must be exactly 2 letters"),
    state: yup
      .string()
      .label("State")
      .when("country", {
        is:        value => value === "US" || value === "CA",
        then:      yup.string().required().typeError("State is a required field"),
        otherwise: yup.string().nullable()
      })
  })
})

export const legalAddressCountryValidation = yup.object().shape({
  legal_address: yup.object().shape({
    country: yup
      .string()
      .required()
      .label("Country")
      .matches(/^[A-Z]+$/, "Country code must be uppercase letters only")
      .min(2, "Country code must be exactly 2 letters")
      .max(2, "Country code must be exactly 2 letters"),
    state: yup
      .string()
      .label("State")
      .when("country", {
        is:        value => value === "US" || value === "CA",
        then:      yup.string().required().typeError("State is a required field"),
        otherwise: yup.string().nullable()
      })
  }),
  user_profile: yup.object().shape({
    year_of_birth: yup
      .number()
      .min(13 - new Date().getFullYear())
      .label("Year of Birth")
      .required()
  })
})

export const newAccountValidation = yup.object().shape({
  password: newPasswordField.label("Password"),
  username: usernameField
})

export const profileValidation = yup.object().shape({
  user_profile: yup.object().shape({
    gender:        yup.string().label("Gender").nullable(),
    year_of_birth: yup
      .number()
      .min(13 - new Date().getFullYear())
      .label("Year of Birth")
      .required()
  })
})

export const addlProfileFieldsValidation = yup.object().shape({
  user_profile: yup.object().shape({
    company:          yup.string().label("Company").nullable(),
    job_title:        yup.string().label("Job Title").nullable(),
    industry:         yup.string().label("Industry").nullable(),
    job_function:     yup.string().label("Job Function").nullable(),
    company_size:     yup.string().label("Company Size").nullable(),
    years_experience: yup.string().label("Years of Work Experience").nullable(),
    leadership_level: yup.string().label("Leadership Level").nullable()
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
  return foundCountry && foundCountry.states && foundCountry.states.length > 0 ?
    foundCountry.states :
    null
}

const renderYearOfBirthField = errors => {
  const hasError =
    errors && errors.user_profile && errors.user_profile.year_of_birth
  return (
    <div>
      <CardLabel
        htmlFor="user_profile.year_of_birth"
        isRequired={true}
        label="Year of Birth"
      />
      <Field
        component="select"
        name="user_profile.year_of_birth"
        id="user_profile.year_of_birth"
        className="form-control"
        autoComplete="bday-year"
        aria-invalid={hasError ? "true" : null}
        aria-describedby={hasError ? "year-of-birth-error" : null}
        required
        title="Select your year of birth."
      >
        <option value="">-----</option>
        {reverse(range(seedYear - 120, seedYear - 13)).map((year, i) => (
          <option key={i} value={year}>
            {year}
          </option>
        ))}
      </Field>
      <ErrorMessage
        id="year-of-birth-error"
        name="user_profile.year_of_birth"
        component={FormError}
      />
    </div>
  )
}

export const LegalAddressCountryFields = ({
  errors,
  countries,
  values
}: LegalAddressProps) => {
  const addressErrors = errors && errors.legal_address
  const [showYearOfBirthField, setShowYearOfBirthField] = React.useState(
    values.user_profile.year_of_birth === ""
  )
  // Show country field if country is not set, or if it's set to US or CA, and no state is selected
  const [showCountryField, setShowCountryField] = React.useState(
    values.legal_address.country === "" ||
      ((values.legal_address.country === "US" ||
        values.legal_address.country === "CA") &&
        !values.legal_address.state)
  )

  React.useEffect(() => {
    if (values.user_profile.year_of_birth === "") {
      setShowYearOfBirthField(true)
    }
    if (
      values.legal_address.country === "" ||
      ((values.legal_address.country === "US" ||
        values.legal_address.country === "CA") &&
        !values.legal_address.state)
    ) {
      setShowCountryField(true)
    }
  }, [values.user_profile.year_of_birth, values.legal_address.country])

  return (
    <React.Fragment>
      {showYearOfBirthField ? (
        <div className="form-group">{renderYearOfBirthField(errors)}</div>
      ) : null}
      {showCountryField ? (
        <div>
          <div className="form-group">
            <CardLabel
              htmlFor="legal_address.country"
              isRequired={true}
              label="Country"
            />
            <Field
              component="select"
              name="legal_address.country"
              id="legal_address.country"
              aria-invalid={
                addressErrors && addressErrors.country ? "true" : null
              }
              aria-describedby={
                addressErrors && addressErrors.country ? "country-error" : null
              }
              className="form-control"
              autoComplete="country"
              required
              title="The country where you live."
            >
              <option value="">-----</option>
              {countries ?
                countries.map((country, i) => (
                  <option key={i} value={country.code}>
                    {country.name}
                  </option>
                )) :
                null}
            </Field>
            <ErrorMessage
              id="country-error"
              name="legal_address.country"
              component={FormError}
            />
          </div>
          {findStates(values.legal_address.country, countries) ? (
            <div className="form-group">
              <CardLabel
                htmlFor="legal_address.state"
                isRequired={true}
                label="State"
              />
              <Field
                component="select"
                name="legal_address.state"
                id="legal_address.state"
                aria-invalid={
                  addressErrors && addressErrors.state ? "true" : null
                }
                aria-describedby={
                  addressErrors && addressErrors.state ? "state-error" : null
                }
                aria-description="The state, territory, or province where you live."
                className="form-control"
                autoComplete="state"
                title="The state, territory, or province where you live."
                required
              >
                <option value="">-----</option>
                {findStates(values.legal_address.country, countries) ?
                  findStates(values.legal_address.country, countries).map(
                    (state, i) => (
                      <option key={i} value={state.code}>
                        {state.name}
                      </option>
                    )
                  ) :
                  null}
              </Field>
              <ErrorMessage
                id="state-error"
                name="legal_address.state"
                component={FormError}
              />
            </div>
          ) : null}
        </div>
      ) : null}
    </React.Fragment>
  )
}

export const LegalAddressFields = ({
  errors,
  countries,
  isNewAccount,
  values
}: LegalAddressProps) => {
  const addressErrors = errors && errors.legal_address
  return (
    <React.Fragment>
      <div className="form-group">
        <CardLabel
          htmlFor="legal_address.first_name"
          isRequired={true}
          label="First Name"
          subLabel="Name that will appear on emails"
        />
        <Field
          type="text"
          name="legal_address.first_name"
          id="legal_address.first_name"
          className="form-control"
          autoComplete="given-name"
          aria-invalid={
            addressErrors && addressErrors.first_name ? "true" : null
          }
          aria-describedby={
            addressErrors && addressErrors.first_name ?
              "first-name-error" :
              null
          }
          aria-description="Name cannot start with, or contain, a special character"
          title="Name cannot start with, or contain, a special character."
          required
        />
        <ErrorMessage
          id="first-name-error"
          name="legal_address.first_name"
          component={FormError}
        />
      </div>
      <div className="form-group">
        <CardLabel
          htmlFor="legal_address.last_name"
          isRequired={true}
          label="Last Name"
        />
        <Field
          type="text"
          name="legal_address.last_name"
          id="legal_address.last_name"
          className="form-control"
          autoComplete="family-name"
          aria-invalid={
            addressErrors && addressErrors.last_name ? "true" : null
          }
          aria-describedby={
            addressErrors && addressErrors.last_name ? "last-name-error" : null
          }
          aria-description="Name cannot start with, or contain, a special character"
          required
        />
        <ErrorMessage name="legal_address.last_name" component={FormError} />
      </div>
      <div className="form-group">
        <CardLabel
          htmlFor="name"
          isRequired={true}
          label="Full Name"
          subLabel="Name that will appear on your certificates"
        />
        <Field
          type="text"
          name="name"
          id="name"
          className="form-control"
          autoComplete="name"
          aria-invalid={errors.name ? "true" : null}
          aria-describedby={errors.name ? "full-name-error" : null}
          aria-label="Full Name"
          aria-description="Name that will appear on your certificates"
        />
        <ErrorMessage name="name" component={FormError} />
      </div>
      {isNewAccount ? (
        <React.Fragment>
          <div className="form-group">
            <CardLabel
              htmlFor="username"
              isRequired={true}
              label="Public Username"
              subLabel="Name that will identify you in courses"
            />
            <Field
              type="text"
              name="username"
              className="form-control"
              autoComplete="username"
              id="username"
              aria-invalid={errors.username ? "true" : null}
              aria-describedby={errors.username ? "username-error" : null}
              aria-description="Name that will identify you in courses."
              required
            />
            <ErrorMessage name="username" component={FormError} />
          </div>
          <div className="form-group">
            <CardLabel htmlFor="password" isRequired={true} label="Password" />
            <Field
              type="password"
              name="password"
              id="password"
              aria-invalid={errors.password ? "true" : null}
              aria-describedby={
                errors.password ? "password-error" : "password-subtitle"
              }
              className="form-control"
              autoComplete="new-password"
              required
            />
            <ErrorMessage name="password" component={FormError} />
            <div id="password-subtitle" className="label-secondary">
              {passwordFieldErrorMessage}
            </div>
          </div>
        </React.Fragment>
      ) : null}
      <div className="form-group">
        <CardLabel
          htmlFor="legal_address.country"
          isRequired={true}
          label="Country"
        />
        <Field
          component="select"
          name="legal_address.country"
          id="legal_address.country"
          aria-invalid={addressErrors && addressErrors.country ? "true" : null}
          aria-describedby={
            addressErrors && addressErrors.country ? "country-error" : null
          }
          className="form-control"
          autoComplete="country"
          required
          title="The country where you live."
        >
          <option value="">-----</option>
          {countries ?
            countries.map((country, i) => (
              <option key={i} value={country.code}>
                {country.name}
              </option>
            )) :
            null}
        </Field>
        <ErrorMessage
          id="country-error"
          name="legal_address.country"
          component={FormError}
        />
      </div>
      {findStates(values.legal_address.country, countries) ? (
        <div className="form-group">
          <CardLabel
            htmlFor="legal_address.state"
            isRequired={true}
            label="State"
          />
          <Field
            component="select"
            name="legal_address.state"
            id="legal_address.state"
            aria-invalid={addressErrors && addressErrors.state ? "true" : null}
            aria-describedby={
              addressErrors && addressErrors.state ? "state-error" : null
            }
            aria-description="The state, territory, or province where you live."
            className="form-control"
            autoComplete="state"
            title="The state, territory, or province where you live."
            required
          >
            <option value="">-----</option>
            {findStates(values.legal_address.country, countries) ?
              findStates(values.legal_address.country, countries).map(
                (state, i) => (
                  <option key={i} value={state.code}>
                    {state.name}
                  </option>
                )
              ) :
              null}
          </Field>
          <ErrorMessage
            id="state-error"
            name="legal_address.state"
            component={FormError}
          />
        </div>
      ) : null}
      {isNewAccount ? (
        <div className="form-group">{renderYearOfBirthField(errors)}</div>
      ) : null}
    </React.Fragment>
  )
}

export const GenderAndDOBProfileFields = errors => {
  return (
    <React.Fragment>
      <div className="row small-gap">
        <div className="col">
          <div className="form-group">
            <CardLabel htmlFor="user_profile.gender" label="Gender" />

            <Field
              component="select"
              name="user_profile.gender"
              id="user_profile.gender"
              className="form-control"
              title="Select your gender."
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
        </div>
        <div className="col">
          <div className="form-group">{renderYearOfBirthField(errors)}</div>
        </div>
      </div>
    </React.Fragment>
  )
}

export const AddlProfileFields = ({
  errors,
  values,
  requireAddlFields
}: AddlProfileFieldsProps) => (
  <React.Fragment>
    <div className="form-group">
      <div className="row">
        <div className="col">
          <CardLabel
            htmlFor="user_profile.highest_education"
            isRequired={requireAddlFields}
            label="Highest Level of Education"
          />
          <Field
            component="select"
            name="user_profile.highest_education"
            id="user_profile.highest_education"
            className="form-control"
            required={requireAddlFields}
            aria-invalid={
              errors &&
              errors.user_profile &&
              errors.user_profile.highest_education ?
                "true" :
                null
            }
            aria-describedby={
              errors &&
              errors.user_profile &&
              errors.user_profile.highest_education ?
                "highest-educaton-level-error-message" :
                null
            }
            title="Select the highest level of education you have completed."
          >
            <option value="">-----</option>
            {HIGHEST_EDUCATION_CHOICES.map((level, i) => (
              <option key={i} value={level}>
                {level}
              </option>
            ))}
          </Field>
          <ErrorMessage
            id="highest-educaton-level-error-message"
            name="user_profile.highest_education"
            component={FormError}
          />
        </div>
      </div>
    </div>
    <div className="form-group small-gap">
      <CardLabel
        htmlFor="occupation-label"
        id="occupation-label"
        isRequired={requireAddlFields}
        label="Are you a"
      />
      <ErrorMessage
        name="user_profile.type_is_student"
        id="user_profile.type_is_studentError"
        component={FormError}
      />
    </div>
    <div className="row small-gap profile-student-type">
      <div className="col-6">
        <div className="form-check">
          <Field
            type="checkbox"
            name="user_profile.type_is_student"
            id="user_profile.type_is_student"
            className="form-check-input"
            aria-labelledby="occupation-label student-label"
            aria-invalid={
              errors &&
              errors.user_profile &&
              errors.user_profile.type_is_student ?
                "true" :
                null
            }
            aria-describedby={
              errors &&
              errors.user_profile &&
              errors.user_profile.type_is_student ?
                "user_profile.type_is_studentError" :
                null
            }
            title="Select if you are a student."
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
            aria-invalid={
              errors &&
              errors.user_profile &&
              errors.user_profile.type_is_professional ?
                "true" :
                null
            }
            aria-describedby={
              errors &&
              errors.user_profile &&
              errors.user_profile.type_is_professional ?
                "user_profile.type_is_studentError" :
                null
            }
            title="Select if you are a professional."
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
      <div className="col-5">
        <div className="form-check">
          <Field
            type="checkbox"
            name="user_profile.type_is_educator"
            id="user_profile.type_is_educator"
            className="form-check-input"
            aria-labelledby="occupation-label educator-label"
            aria-invalid={
              errors &&
              errors.user_profile &&
              errors.user_profile.type_is_educator ?
                "true" :
                null
            }
            aria-describedby={
              errors &&
              errors.user_profile &&
              errors.user_profile.type_is_educator ?
                "user_profile.type_is_studentError" :
                null
            }
            title="Select if you are an educator."
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
            aria-invalid={
              errors && errors.user_profile && errors.user_profile.type_is_other ?
                "true" :
                null
            }
            aria-describedby={
              errors && errors.user_profile && errors.user_profile.type_is_other ?
                "user_profile.type_is_studentError" :
                null
            }
            title="Select if you are in an occupation not shown."
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
    {values.user_profile.type_is_professional ? (
      <React.Fragment>
        <Field
          type="hidden"
          name="user_profile.addl_fields_flag"
          value={true}
        />
        <div className="form-group">
          <CardLabel htmlFor="user_profile.company" label="Company" />
          <Field
            type="text"
            name="user_profile.company"
            id="user_profile.company"
            autoComplete="organization"
            aria-describedby="user_profile.companyError"
            className="form-control"
            title="The name of the company you work for."
          />
          <ErrorMessage
            name="user_profile.company"
            id="user_profile.companyError"
            component={FormError}
          />
        </div>
        <div className="row small-gap">
          <div className="col">
            <div className="form-group">
              <CardLabel htmlFor="user_profile.job_title" label="Job Title" />
              <Field
                type="text"
                name="user_profile.job_title"
                id="user_profile.job_title"
                autoComplete="organization-title"
                aria-describedby="user_profile.job_title_error"
                className="form-control"
                title="Your job title at your company."
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
              <CardLabel
                htmlFor="user_profile.company_size"
                label="Company Size"
              />
              <Field
                component="select"
                name="user_profile.company_size"
                id="user_profile.company_size"
                className="form-control"
                title="Select the size of the company you work for."
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
        <div className="row small-gap">
          <div className="col">
            <div className="form-group">
              <CardLabel htmlFor="user_profile.industry" label="Industry" />
              <Field
                component="select"
                name="user_profile.industry"
                id="user_profile.industry"
                className="form-control"
                title="Select the industry you work in."
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
              <CardLabel
                htmlFor="user_profile.job_function"
                label="Job Function"
              />
              <Field
                component="select"
                name="user_profile.job_function"
                id="user_profile.job_function"
                className="form-control"
                title="Select the function that best matches your job role."
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
        <div className="row small-gap">
          <div className="col">
            <div className="form-group">
              <CardLabel
                htmlFor="user_profile.years_experience"
                label="Years of Work Experience"
              />
              <Field
                component="select"
                name="user_profile.years_experience"
                id="user_profile.years_experience"
                className="form-control"
                title="Select the number of years of work experience you have."
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
              <CardLabel
                htmlFor="user_profile.leadership_level"
                label="Leadership Level"
              />
              <Field
                component="select"
                name="user_profile.leadership_level"
                id="user_profile.leadership_level"
                className="form-control"
                title="Select your leadership level."
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
