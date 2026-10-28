// @flow
import React from "react"
import { Formik, Form } from "formik"
import { ConnectedFocusError } from "focus-formik-error"

import {
  LegalAddressComplianceFields,
  LegalAddressCountryFields,
  complianceAddressValidation,
  legalAddressCountryValidation
} from "./ProfileFormFields"

import type { User, Country } from "../../flow/authTypes"

type Props = {
  onSubmit: Function,
  user: User,
  countries: Array<Country>,
  requireComplianceFields?: boolean,
  // Fields checkout rejected, shown and flagged even when filled in
  rejectedFields?: Array<string>
}

const getInitialValues = (user: User) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address,
  user_profile:  {
    year_of_birth: (user.user_profile && user.user_profile.year_of_birth) || ""
  }
})

const AddlProfileFieldsForm = ({
  onSubmit,
  user,
  countries,
  requireComplianceFields,
  rejectedFields
}: Props) => {
  const validation = requireComplianceFields ?
    complianceAddressValidation :
    legalAddressCountryValidation

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={validation}
      initialValues={getInitialValues(user)}
      validateOnChange={false}
      validateOnBlur={false}
    >
      {({ isSubmitting, values, errors }) => {
        return (
          <Form noValidate>
            <ConnectedFocusError />
            <LegalAddressCountryFields
              errors={errors}
              countries={countries}
              values={values}
              rejectedFields={rejectedFields}
            />
            {requireComplianceFields ? (
              <LegalAddressComplianceFields
                errors={errors}
                values={values}
                rejectedFields={rejectedFields}
              />
            ) : null}
            <div className="row submit-row no-gutters">
              <div className="col d-flex justify-content-end">
                <button
                  type="submit"
                  className="btn btn-primary btn-gradient-red-to-blue"
                  disabled={isSubmitting}
                >
                  Submit
                </button>
              </div>
            </div>
          </Form>
        )
      }}
    </Formik>
  )
}

export default AddlProfileFieldsForm
