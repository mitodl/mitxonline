// @flow
import React from "react"
import { Formik, Form } from "formik"

import { legalAddressValidation, LegalAddressFields } from "./ProfileFormFields"

import type { Country, User } from "../../flow/authTypes"

type Props = {
  onSubmit: Function,
  countries: Array<Country>,
  user: User
}

const getInitialValues = (user: User) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address
})

const EditProfileForm = ({ onSubmit, countries, user }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={legalAddressValidation}
    initialValues={getInitialValues(user)}
    render={({ isSubmitting, setFieldValue, setFieldTouched, values }) => (
      <Form>
        <LegalAddressFields
          countries={countries}
          setFieldValue={setFieldValue}
          setFieldTouched={setFieldTouched}
          values={values}
          includePassword={false}
        />
        <div className="row submit-row no-gutters justify-content-end">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={isSubmitting}
          >
            Submit
          </button>
        </div>
      </Form>
    )}
  />
)

export default EditProfileForm
