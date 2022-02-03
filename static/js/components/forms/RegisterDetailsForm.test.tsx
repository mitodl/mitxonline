import { assert } from "chai"
import { noop } from "lodash"
import sinon from "sinon"
import wait from "waait"
import {
  findFormikErrorByName,
  findFormikFieldByName
} from "../../lib/test_utils"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import RegisterDetailsForm from "./RegisterDetailsForm"

describe("RegisterDetailsForm", () => {
  let helper: IntegrationTestHelper,
    renderForm: TestRenderer,
    onSubmitStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    helper.mockGetRequest("/api/countries/", [])
    onSubmitStub = helper.sandbox.stub()
    renderForm = helper.configureRenderer(RegisterDetailsForm, {
      onSubmit: onSubmitStub
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("passes onSubmit to Formik", async () => {
    const { wrapper } = await renderForm()
    assert.equal(wrapper.find("Formik").props().onSubmit, onSubmitStub)
  })

  it("renders the form", async () => {
    const { wrapper } = await renderForm()
    const form = wrapper.find("Formik")
    assert.ok(findFormikFieldByName(form, "name").exists())
    assert.ok(findFormikFieldByName(form, "password").exists())
    assert.ok(form.find("button[type='submit']").exists())
  })
  ;([
    ["password", "", "Password is a required field"],
    ["password", "pass", "Password must be at least 8 characters"],
    ["password", "passwor", "Password must be at least 8 characters"],
    ["password", "password123", null],
    [
      "password",
      "password",
      "Password must contain at least one letter and number"
    ],
    ["name", "", "Full Name is a required field"],
    ["name", "  ", "Full Name is a required field"],
    ["name", "Jane", null],
    ["username", "", "Username is a required field"],
    ["username", "  ", "Username is a required field"],
    ["username", "ab", "Username must be at least 3 characters"],
    [
      "username",
      "0123456789012345678901234567890",
      "Username must be at most 30 characters"
    ],
    ["username", "ábc-dèf-123", null],
    ["legal_address.first_name", "", "First Name is a required field"],
    ["legal_address.last_name", "", "Last Name is a required field"]
  ] as [string, string, string | null][]).forEach(
    ([name, value, errorMessage]) => {
      it(`validates the field name=${name}, value=${JSON.stringify(
        value
      )} and expects error=${JSON.stringify(errorMessage)}`, async () => {
        const { wrapper } = await renderForm()
        const input = wrapper.find(`input[name="${name}"]`)
        input.simulate("change", {
          persist: noop,
          target:  {
            name,
            value
          }
        })
        input.simulate("blur")
        await wait(5)
        wrapper.update()
        assert.deepEqual(
          findFormikErrorByName(wrapper, name).text(),
          errorMessage
        )
      })
    }
  )
  ;[
    ["name", "name"],
    ["legal_address.first_name", "given-name"],
    ["legal_address.last_name", "family-name"],
    ["legal_address.country", "country"]
  ].forEach(([formFieldName, autoCompleteName]) => {
    it(`validates that autoComplete=${autoCompleteName} for field ${formFieldName}`, async () => {
      const { wrapper } = await renderForm()
      const form = wrapper.find("Formik")
      assert.equal(
        findFormikFieldByName(form, formFieldName).prop("autoComplete"),
        autoCompleteName
      )
    })
  })
  // Tests name regex for first & last name
  const invalidNameMessage =
    "Name cannot start with a special character (~!@&)(+:'.?/,`-), and cannot contain any of (/^$#*=[]`%_;<>{}|\")"

  ;["legal_address.first_name", "legal_address.last_name"].forEach(
    fieldName => {
      // List of valid character but they couldn't exist in the start of name
      [
        "~",
        "!",
        "@",
        "&",
        ")",
        "(",
        "+",
        ":",
        ".",
        "?",
        "/",
        ",",
        "`",
        "-"
      ].forEach(validCharacter => {
        it(`validates the field name=${fieldName}, value=${JSON.stringify(
          `${validCharacter}Name`
        )} and expects error=${JSON.stringify(
          invalidNameMessage
        )}`, async () => {
          // Prepend the character to start of the name value
          const value = `${validCharacter}Name`

          const { wrapper } = await renderForm()
          const field = wrapper.find(`input[name="${fieldName}"]`)
          field.simulate("change", {
            persist: noop,
            target:  {
              name:  fieldName,
              value: value
            }
          })
          field.simulate("blur")
          await wait(5)
          wrapper.update()
          assert.deepEqual(
            findFormikErrorByName(wrapper, fieldName).text(),
            invalidNameMessage
          )
        })
      })

      // List of invalid characters that cannot exist anywhere in name
      ;[
        "/",
        "^",
        "$",
        "#",
        "*",
        "=",
        "[",
        "]",
        "`",
        "%",
        "_",
        ";",
        "<",
        ">",
        "{",
        "}",
        '"',
        "|"
      ].forEach(invalidCharacter => {
        it(`validates the field name=${fieldName}, value=${JSON.stringify(
          `${invalidCharacter}Name${invalidCharacter}`
        )} and expects error=${JSON.stringify(
          invalidNameMessage
        )}`, async () => {
          // Prepend the character to start if the name value
          const value = `${invalidCharacter}Name${invalidCharacter}`

          const { wrapper } = await renderForm()
          const field = wrapper.find(`input[name="${fieldName}"]`)
          field.simulate("change", {
            persist: noop,
            target:  {
              name:  fieldName,
              value: value
            }
          })
          field.simulate("blur")
          await wait(5)
          wrapper.update()
          assert.deepEqual(
            findFormikErrorByName(wrapper, fieldName).text(),
            invalidNameMessage
          )
        })
      })
    }
  )
})
