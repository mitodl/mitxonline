// @flow
import React from "react"
import { Formik, Form } from "formik"

import {
  newAccountValidation,
  legalAddressValidation,
  LegalAddressFields
} from "./ProfileFormFields"

import type { Country } from "../../flow/authTypes"

type Props = {
  onSubmit: Function,
  countries: Array<Country>
}

const INITIAL_VALUES = {
  name:          "",
  password:      "",
  username:      "",
  legal_address: {
    first_name: "",
    last_name:  "",
    country:    ""
  }
}

const RegisterDetailsForm = ({ onSubmit, countries }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={legalAddressValidation.concat(newAccountValidation)}
    initialValues={INITIAL_VALUES}
    render={({ isSubmitting, setFieldValue, setFieldTouched, values }) => (
      <Form>
        <LegalAddressFields
          countries={countries}
          setFieldValue={setFieldValue}
          setFieldTouched={setFieldTouched}
          values={values}
          isNewAccount={true}
        />
        <div className="row submit-row no-gutters justify-content-end">
          <button
            type="submit"
            className="btn btn-primary btn-gradient-red large"
            disabled={isSubmitting}
          >
            Continue
          </button>
        </div>
      </Form>
    )}
  />
)

export default RegisterDetailsForm
