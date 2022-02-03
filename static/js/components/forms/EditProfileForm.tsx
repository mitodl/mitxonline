import { Form, Formik } from "formik"
import React from "react"
import useCountries from "../../hooks/countries"
import { LoggedInUser } from "../../types/auth"
import { LegalAddressFields, legalAddressValidation } from "./ProfileFormFields"

type Props = {
  onSubmit: (...args: Array<any>) => any
  user: LoggedInUser | null
}

const getInitialValues = (user: LoggedInUser) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address
})

export default function EditProfileForm({ onSubmit, user }: Props) {
  const {
    countries,
    state: { isFinished }
  } = useCountries()

  if (!user || !isFinished) return null

  return (
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
            isNewAccount={false}
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
}
