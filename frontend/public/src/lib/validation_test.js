// @flow
import { assert } from "chai"
import { ValidationError } from "yup"

import {
  changePasswordFormValidation,
  resetPasswordFormValidation,
  usernameField
} from "./validation"

describe("validation utils", () => {
  describe("resetPasswordFormValidation", () => {
    it(`should validate with matching passwords`, async () => {
      const inputs = {
        newPassword:                   "password1",
        confirmPasswordChangePassword: "password1"
      }
      const result = await resetPasswordFormValidation.validate(inputs)

      assert.deepEqual(result, inputs)
    })

    it(`Reset password form validation should throw an error with different newPassword and confirmPassword values.`, async () => {
      const inputs = {
        newPassword:                   "password1",
        confirmPasswordChangePassword: "password2"
      }
      const promise = resetPasswordFormValidation.validate(inputs)

      const result = await assert.isRejected(promise, ValidationError)

      assert.deepEqual(result.errors, [
        "New password and Confirm New Password must match."
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

    it(`Change password form validation should throw an error with different new and Confirm New Password values.`, async () => {
      const inputs = {
        currentPassword:               "old-password",
        newPassword:                   "password1",
        confirmPasswordChangePassword: "password2"
      }
      const promise = changePasswordFormValidation.validate(inputs)

      const result = await assert.isRejected(promise, ValidationError)

      assert.deepEqual(result.errors, [
        "New password and Confirm New Password must match."
      ])
    })
  })

  describe("usernameField validation", () => {
    it("should pass for a valid username", async () => {
      const result = await usernameField.validate("validUser123")
      assert.equal(result, "validUser123")
    })

    it("should fail for username shorter than 3 characters", async () => {
      const promise = usernameField.validate("ab")
      const error = await assert.isRejected(promise, ValidationError)
      assert.include(
        error.errors[0],
        "Username must be between 3 and 30 characters."
      )
    })

    it("should fail for username longer than 30 characters", async () => {
      const longUsername = "a".repeat(31)
      const promise = usernameField.validate(longUsername)
      const error = await assert.isRejected(promise, ValidationError)
      assert.include(
        error.errors[0],
        "Username must be between 3 and 30 characters."
      )
    })

    it('should fail for username containing "@" symbol', async () => {
      const promise = usernameField.validate("user@name")
      const error = await assert.isRejected(promise, ValidationError)
      assert.include(error.errors[0], 'Username cannot contain the "@" symbol')
    })

    it("should fail for empty username", async () => {
      const promise = usernameField.validate("")
      const error = await assert.isRejected(promise, ValidationError)
      assert.include(error.errors[0], "Public Username is a required field")
    })
  })
})
