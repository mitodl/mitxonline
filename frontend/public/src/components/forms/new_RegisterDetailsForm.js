// @flow
import React from "react"
import { Formik, Form } from "formik"

import {
  legalAddressValidation,
  profileValidation,
  LegalAddressFields
} from "./new_ProfileFormFields"

import type { Country } from "../../flow/authTypes"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  onSubmit: Function,
  countries: Array<Country>
}

const INITIAL_VALUES = {
  name:          "",
  username:      "",
  legal_address: {
    first_name: "",
    last_name:  "",
    country:    "",
    state:      ""
  },
  user_profile: {
    year_of_birth: ""
  }
}

const RegisterDetailsForm = ({ onSubmit, countries }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={legalAddressValidation
      .concat(profileValidation)}
    initialValues={INITIAL_VALUES}
    validateOnChange={false}
    validateOnBlur={false}
  >
    {({ values, errors, isSubmitting }) => {
      return (
        <Form noValidate>
          <ConnectedFocusError />
          <LegalAddressFields
            errors={errors}
            countries={countries}
            values={values}
            isNewAccount={true}
          />
          <div className="submit-row">
            <button
              type="submit"
              className="btn btn-primary btn-gradient-red-to-blue large"
              disabled={isSubmitting}
            >
              Continue
            </button>
          </div>
        </Form>
      )
    }}
  </Formik>
)

export default RegisterDetailsForm
