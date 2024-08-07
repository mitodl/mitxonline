// @flow
import React from "react"
import { Formik, Form } from "formik"
import {
  legalAddressValidation,
  profileValidation,
  addlProfileFieldsValidation,
  LegalAddressFields,
  GenderAndDOBProfileFields,
  AddlProfileFields
} from "./ProfileFormFields"

import type { Country, User } from "../../flow/authTypes"
import { ConnectedFocusError } from "focus-formik-error"

type Props = {
  onSubmit: Function,
  countries: Array<Country>,
  user: User
}

const getInitialValues = (user: User) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address,
  user_profile:  {
    gender:          (user.user_profile && user.user_profile.gender) || "",
    addl_field_flag: user.user_profile && user.user_profile.addl_field_flag,
    company:         (user.user_profile && user.user_profile.company) || "",
    company_size:
      (user.user_profile && user.user_profile.company_size) || undefined,
    highest_education:
      (user.user_profile && user.user_profile.highest_education) || "",
    industry:     (user.user_profile && user.user_profile.industry) || "",
    job_function: (user.user_profile && user.user_profile.job_function) || "",
    job_title:    (user.user_profile && user.user_profile.job_title) || "",
    leadership_level:
      (user.user_profile && user.user_profile.leadership_level) || "",
    year_of_birth: (user.user_profile && user.user_profile.year_of_birth) || "",
    years_experience:
      (user.user_profile && user.user_profile.years_experience) || undefined,
    type_is_professional:
      (user.user_profile && user.user_profile.type_is_professional) || false,
    type_is_student:
      (user.user_profile && user.user_profile.type_is_student) || false,
    type_is_educator:
      (user.user_profile && user.user_profile.type_is_educator) || false,
    type_is_other:
      (user.user_profile && user.user_profile.type_is_other) || false
  }
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
      {({ values, errors, isSubmitting }) => {
        return (
          <Form noValidate>
            <ConnectedFocusError />
            <LegalAddressFields
              errors={errors}
              countries={countries}
              values={values}
              isNewAccount={false}
            />
            <GenderAndDOBProfileFields errors={errors} />
            <AddlProfileFields errors={errors} values={values} />
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

export default EditProfileForm
