// @flow
import { assert } from "chai"
import { ValidationError } from "yup"

import {
  changePasswordFormValidation,
  resetPasswordFormValidation,
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

    //
    ;[
      [
        { newPassword: "password1", confirmPassword: "password2" },
        ["Passwords must match"]
      ]
    ].forEach(([inputs, errors]) => {
      it(`should throw an error with inputs=${JSON.stringify(
        inputs
      )}`, async () => {
        const promise = resetPasswordFormValidation.validate(inputs)

        const result = await assert.isRejected(promise, ValidationError)

        assert.deepEqual(result.errors, errors)
      })
    })
  })

  describe("ChangePasswordFormValidation", () => {
    it(`should validate with matching passwords`, async () => {
      const inputs = {
        oldPassword:     "old-password",
        newPassword:     "password1",
        confirmPassword: "password1"
      }
      const result = await changePasswordFormValidation.validate(inputs)

      assert.deepEqual(result, inputs)
    })

    //
    ;[
      [
        {
          oldPassword:     "password1",
          newPassword:     "password1",
          confirmPassword: "password2"
        },
        ["Passwords must match"]
      ]
    ].forEach(([inputs, errors]) => {
      it(`should throw an error with inputs=${JSON.stringify(
        inputs
      )}`, async () => {
        const promise = changePasswordFormValidation.validate(inputs)

        const result = await assert.isRejected(promise, ValidationError)

        assert.deepEqual(result.errors, errors)
      })
    })
  })
})
