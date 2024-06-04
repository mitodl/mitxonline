// @flow
import { assert } from "chai"
import { ValidationError } from "yup"

import {
  changePasswordFormValidation,
  resetPasswordFormValidation
} from "./validation"

describe("validation utils", () => {
  describe("resetPasswordFormValidation", () => {
    it(`should validate with matching passwords`, async () => {
      const inputs = {
        newPassword:     "password1",
        confirmPassword: "password1"
      }
      const result = await resetPasswordFormValidation.validate(inputs)

      assert.deepEqual(result, inputs)
    })

    it(`Reset password form validation should throw an error with different newPassword and confirmPassword values.`, async () => {
      const inputs = {
        newPassword:     "password1",
        confirmPassword: "password2"
      }
      const promise = resetPasswordFormValidation.validate(inputs)

      const result = await assert.isRejected(promise, ValidationError)

      assert.deepEqual(result.errors, [
        "New password and Confirm Password must match."
      ])
    })
  })

  describe("ChangePasswordFormValidation", () => {
    it(`Change password form validation should pass with matching passwords`, async () => {
      const inputs = {
        currentPassword:               "old-password",
        newPassword:                   "password1",
        confirmPasswordChangePassword: "password1"
      }
      const result = await changePasswordFormValidation.validate(inputs)

      assert.deepEqual(result, inputs)
    })

    it(`Change password form validation should throw an error with different new and confirm password values.`, async () => {
      const inputs = {
        currentPassword:               "old-password",
        newPassword:                   "password1",
        confirmPasswordChangePassword: "password2"
      }
      const promise = changePasswordFormValidation.validate(inputs)

      const result = await assert.isRejected(promise, ValidationError)

      assert.deepEqual(result.errors, [
        "New password and Confirm Password must match."
      ])
    })
  })
})
