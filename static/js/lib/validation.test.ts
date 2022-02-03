import { ValidationError } from "yup"
import {
  changeEmailFormValidation,
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
      expect(result).toEqual(inputs)
    })
    ;[
      [
        {
          newPassword:     "",
          confirmPassword: ""
        },
        ["Confirm Password is a required field"]
      ],
      [
        {
          newPassword:     "password1",
          confirmPassword: "password2"
        },
        ["Passwords must match"]
      ]
    ].forEach(([inputs, errors]) => {
      it(`should throw an error with inputs=${JSON.stringify(
        inputs
      )}`, async () => {
        try {
          await resetPasswordFormValidation.validate(inputs)
        } catch (e) {
          expect(e).toBeInstanceOf(ValidationError)
          expect((e as ValidationError).errors).toEqual(errors)
        }
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
      expect(result).toEqual(inputs)
    })
    ;[
      [
        {
          oldPassword:     "",
          newPassword:     "password1",
          confirmPassword: "password1"
        },
        ["Old Password is a required field"]
      ],
      [
        {
          oldPassword:     "password1",
          newPassword:     "",
          confirmPassword: ""
        },
        ["Confirm Password is a required field"]
      ],
      [
        {
          oldPassword:     "password1",
          newPassword:     "password1",
          confirmPassword: "password2"
        },
        ["Passwords must match"]
      ],
      [
        {
          oldPassword:     "password1",
          newPassword:     "pass",
          confirmPassword: "pass"
        },
        ["New Password must be at least 8 characters"]
      ],
      [
        {
          oldPassword:     "password1",
          newPassword:     "password",
          confirmPassword: "password"
        },
        ["Password must contain at least one letter and number"]
      ]
    ].forEach(([inputs, errors]) => {
      it(`should throw an error with inputs=${JSON.stringify(
        inputs
      )}`, async () => {
        try {
          await changePasswordFormValidation.validate(inputs)
        } catch (e) {
          expect(e).toBeInstanceOf(ValidationError)
          expect((e as ValidationError).errors).toEqual(errors)
        }
      })
    })
  })

  describe("ChangeEmailFormValidation", () => {
    it(`should validate with different email`, async () => {
      const inputs = {
        email:           "test@example.com",
        confirmPassword: "password1"
      }
      const result = await changeEmailFormValidation.validate(inputs, {
        context: {
          currentEmail: "abc@example.com"
        }
      })
      expect(result).toEqual(inputs)
    })
    ;[
      [
        {
          email:           "abc@example.com",
          confirmPassword: "password"
        },
        ["Email cannot be the same. Please use a different one."]
      ],
      [
        {
          email:           "test@example.com",
          confirmPassword: ""
        },
        ["Confirm Password is a required field"]
      ],
      [
        {
          email:           "test@example.com",
          confirmPassword: "abcd"
        },
        ["Confirm Password must be at least 8 characters"]
      ]
    ].forEach(([inputs, errors]) => {
      it(`should throw an error with inputs=${JSON.stringify(
        inputs
      )}`, async () => {
        expect.assertions(2)
        try {
          await changeEmailFormValidation.validate(inputs, {
            context: {
              currentEmail: "abc@example.com"
            }
          })
        } catch (e) {
          expect(e).toBeInstanceOf(ValidationError)
          expect((e as ValidationError).errors).toEqual(errors)
        }
      })
    })
  })
})
