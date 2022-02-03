import { Form, Formik, FormikConfig } from "formik"
import React from "react"
import useCountries from "../../hooks/countries"
import {
  LegalAddressFields,
  legalAddressValidation,
  newAccountValidation
} from "./ProfileFormFields"

type Props = {
  onSubmit: FormikConfig<typeof INITIAL_VALUES>["onSubmit"]
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

const RegisterDetailsForm = ({ onSubmit }: Props) => {
  const { countries } = useCountries()
  return (
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
}

export default RegisterDetailsForm
