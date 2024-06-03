// @flow
import React from "react"
import { Formik, Form } from "formik"
import { ConnectedFocusError } from "focus-formik-error"
import * as yup from "yup"

import {
  GenderAndDOBProfileFields,
  AddlProfileFields,
  profileValidation,
  addlProfileFieldsValidation
} from "./ProfileFormFields"

import type { User } from "../../flow/authTypes"

type Props = {
  onSubmit: Function,
  user: User,
  requireTypeFields: ?boolean
}

const getInitialValues = (user: User) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address,
  user_profile:  {
    gender:               user.user_profile.gender || "",
    addl_field_flag:      user.user_profile.addl_field_flag,
    company:              user.user_profile.company || "",
    company_size:         user.user_profile.company_size || null,
    highest_education:    user.user_profile.highest_education || null,
    industry:             user.user_profile.industry || null,
    job_function:         user.user_profile.job_function || null,
    job_title:            user.user_profile.job_title || null,
    leadership_level:     user.user_profile.leadership_level || null,
    year_of_birth:        user.user_profile.year_of_birth || null,
    years_experience:     user.user_profile.years_experience || null,
    type_is_professional: user.user_profile.type_is_professional || false,
    type_is_student:      user.user_profile.type_is_student || false,
    type_is_educator:     user.user_profile.type_is_educator || false,
    type_is_other:        user.user_profile.type_is_other || false
  }
})

const AddlProfileFieldsForm = ({
  onSubmit,
  user,
  requireTypeFields
}: Props) => {
  let validation = profileValidation.concat(addlProfileFieldsValidation)

  const occupationField = yup
    .boolean()
    .test(
      "one occupation must be selected",
      "At least one occupation must be selected",
      function() {
        return (
          this.parent.type_is_student ||
          this.parent.type_is_professional ||
          this.parent.type_is_educator ||
          this.parent.type_is_other
        )
      }
    )

  if (requireTypeFields) {
    validation = validation.concat(
      yup.object().shape({
        user_profile: yup.object().shape({
          highest_education: yup
            .string()
            .required("Highest Level of Education is a required field")
            .typeError("Highest Level of Education is a required field"),
          type_is_student:      occupationField,
          type_is_professional: occupationField,
          type_is_educator:     occupationField,
          type_is_other:        occupationField
        })
      })
    )
  }

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
            <GenderAndDOBProfileFields errors={errors} />
            <AddlProfileFields
              values={values}
              isNewAccount={false}
              requireAddlFields={requireTypeFields}
              errors={errors}
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
      }}
    </Formik>
  )
}

export default AddlProfileFieldsForm
