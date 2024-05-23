// @flow
import React from "react"
import { Formik, Form } from "formik"
import * as yup from "yup"

import {
  ProfileFields,
  AddlProfileFields,
  profileValidation,
  addlProfileFieldsValidation,
  requireLearnerTypeFields
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
    gender:            user.user_profile.gender || "",
    addl_field_flag:   user.user_profile.addl_field_flag,
    company:           user.user_profile.company || "",
    company_size:      user.user_profile.company_size || "",
    highest_education: user.user_profile.highest_education || "",
    industry:          user.user_profile.industry || "",
    job_function:      user.user_profile.job_function || "",
    job_title:         user.user_profile.job_title || "",
    leadership_level:  user.user_profile.leadership_level || "",
    year_of_birth:     user.user_profile.year_of_birth || "",
    years_experience:  user.user_profile.years_experience || "",
  }
})

const AddlProfileFieldsForm = ({
  onSubmit,
  user,
  requireTypeFields
}: Props) => {
  let validation = profileValidation.concat(addlProfileFieldsValidation)

  if (requireTypeFields) {
    validation = validation.concat(
      yup.object().shape({
        user_profile: yup.object().shape({
          highest_education: yup
            .string()
            .required("Highest Level of Education is a required field")
            .typeError("Highest Level of Education is a required field"),
          type_is_student: yup.boolean().test(requireLearnerTypeFields)
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
      {({ isSubmitting, values }) => {
        return (
          <Form>
            <ProfileFields values={values} isNewAccount={false} />
            <AddlProfileFields
              values={values}
              isNewAccount={false}
              requireAddlFields={requireTypeFields}
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
