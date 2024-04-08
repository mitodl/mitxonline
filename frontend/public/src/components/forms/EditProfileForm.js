// @flow
import React from "react"
import {Formik, Form, Field, ErrorMessage} from "formik"
import {
  legalAddressValidation,
  profileValidation,
  addlProfileFieldsValidation,
  LegalAddressFields,
  ProfileFields,
  AddlProfileFields
} from "./ProfileFormFields"

import type { Country, User } from "../../flow/authTypes"
import {ConnectedFocusError} from "focus-formik-error"

type Props = {
  onSubmit: Function,
  countries: Array<Country>,
  user: User
}

const getInitialValues = (user: User) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address,
  user_profile:  user.user_profile
})

const EditProfileForm = ({ onSubmit, countries, user }: Props) => {
  const validation = legalAddressValidation.concat(profileValidation)
  validation.concat(addlProfileFieldsValidation)

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={validation}
      initialValues={getInitialValues(user)}
      validateOnChange={false}
      validateOnBlur={false}
    >
      {({
        values,
        errors,
        touched,
        isSubmitting,
      }) => {
        return (
          <Form>
            <ConnectedFocusError />
            <LegalAddressFields
              touched={touched}
              errors={errors}
              countries={countries}
              values={values}
              isNewAccount={false}
            />
            <ProfileFields
              touched={touched}
              errors={errors}
              values={values}
              isNewAccount={false}
            />
            <AddlProfileFields
              touched={touched}
              errors={errors}
              values={values}
              isNewAccount={false}
            />
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
      }
      }
    </Formik>
  )
}

export default EditProfileForm
