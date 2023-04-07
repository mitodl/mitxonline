// @flow
import React from "react"
import { Formik, Form } from "formik"
import { checkFeatureFlag } from "../../lib/util"
import {
  legalAddressValidation,
  profileValidation,
  addlProfileFieldsValidation,
  LegalAddressFields,
  ProfileFields,
  AddlProfileFields
} from "./ProfileFormFields"

import type { Country, User } from "../../flow/authTypes"

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

  if (checkFeatureFlag("enable_addl_profile_fields")) {
    validation.concat(addlProfileFieldsValidation)
  }

  return (
    <Formik
      onSubmit={onSubmit}
      validationSchema={validation}
      initialValues={getInitialValues(user)}
      validateOnChange={false}
      validateOnBlur={false}
      render={({ isSubmitting, setFieldValue, setFieldTouched, values }) => (
        <Form>
          <LegalAddressFields
            countries={countries}
            setFieldValue={setFieldValue}
            setFieldTouched={setFieldTouched}
            values={values}
            isNewAccount={false}
          />
          <ProfileFields
            setFieldValue={setFieldValue}
            setFieldTouched={setFieldTouched}
            values={values}
            isNewAccount={false}
          />
          {checkFeatureFlag("enable_addl_profile_fields") ? (
            <AddlProfileFields
              setFieldValue={setFieldValue}
              setFieldTouched={setFieldTouched}
              values={values}
              isNewAccount={false}
            />
          ) : null}
          <div className="row submit-row no-gutters">
            <div className="col d-flex justify-content-end">
              <button
                type="submit"
                className="btn btn-primary"
                disabled={isSubmitting}
              >
                Submit
              </button>
            </div>
          </div>
        </Form>
      )}
    />
  )
}

export default EditProfileForm
