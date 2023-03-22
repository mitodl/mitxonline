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
  user_profile:  user.user_profile
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
      render={({ isSubmitting, setFieldValue, setFieldTouched, values }) => (
        <Form>
          <ProfileFields
            setFieldValue={setFieldValue}
            setFieldTouched={setFieldTouched}
            values={values}
            isNewAccount={false}
          />
          <AddlProfileFields
            setFieldValue={setFieldValue}
            setFieldTouched={setFieldTouched}
            values={values}
            isNewAccount={false}
            requireAddlFields={requireTypeFields}
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

export default AddlProfileFieldsForm
