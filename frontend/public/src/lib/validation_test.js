// @flow
import { assert } from "chai"
import { ValidationError } from "yup"

import {
  changePasswordFormValidation,
  resetPasswordFormValidation,
  passwordFieldRegex,
  usernameFieldRegex
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

  describe("Validation Regex", () => {
    const passwordRegex = new RegExp(passwordFieldRegex)
    const usernameRegex = new RegExp(usernameFieldRegex)
    ;[
      ["", false],
      ["pass", false],
      ["passwor", false],
      ["password123", true],
      ["password", false]
    ].forEach(([value, regexMatch]) => {
      it("password regex pattern matching.", () => {
        assert.equal(passwordRegex.test(value), regexMatch)
      })
    })
    ;[
      ["", false],
      ["  ", false],
      ["ab", false],
      ["0123456789012345678901234567890", false],
      ["ábc-dèf-123", true]
    ].forEach(([value, regexMatch]) => {
      it("username regex pattern matching.", () => {
        assert.equal(usernameRegex.test(value), regexMatch)
      })
    })
  })
})
