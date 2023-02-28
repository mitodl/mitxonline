// @flow
import React from "react"
import { Formik, Form } from "formik"

import {
  ProfileFields,
  AddlProfileFields,
  profileValidation,
  addlProfileFieldsValidation
} from "./ProfileFormFields"

import type { User } from "../../flow/authTypes"

type Props = {
  onSubmit: Function,
  user: User
}

const getInitialValues = (user: User) => ({
  name:          user.name,
  email:         user.email,
  legal_address: user.legal_address,
  user_profile:  user.user_profile
})

const AddlProfileFieldsForm = ({ onSubmit, user }: Props) => (
  <Formik
    onSubmit={onSubmit}
    validationSchema={profileValidation.concat(addlProfileFieldsValidation)}
    initialValues={getInitialValues(user)}
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

export default AddlProfileFieldsForm
