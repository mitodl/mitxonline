import { assert } from "chai"
import { noop } from "lodash"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import wait from "waait"
import { makeCountries, makeUser } from "../../factories/user"
import {
  findFormikErrorByName,
  findFormikFieldByName
} from "../../lib/test_utils"
import IntegrationTestHelper, {
  TestRenderer
} from "../../util/integration_test_helper"
import EditProfileForm from "./EditProfileForm"

describe("EditProfileForm", () => {
  let helper: IntegrationTestHelper,
    renderForm: TestRenderer,
    onSubmitStub: sinon.SinonStub
  const countries = makeCountries()
  const user = makeUser()

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    onSubmitStub = helper.sandbox.stub()
    helper.mockGetRequest("/api/countries/", countries)
    renderForm = helper.configureRenderer(EditProfileForm, {
      onSubmit: onSubmitStub,
      user
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
    assert.isNotOk(findFormikFieldByName(form, "password").exists())
    assert.ok(findFormikFieldByName(form, "legal_address.first_name").exists())
    assert.ok(findFormikFieldByName(form, "legal_address.last_name").exists())
    assert.ok(findFormikFieldByName(form, "legal_address.country").exists())
    assert.ok(form.find("button[type='submit']").exists())
  })
  ;([
    ["legal_address.first_name", "", "First Name is a required field"],
    ["legal_address.first_name", "  ", "First Name is a required field"],
    ["legal_address.first_name", "Jane", null],
    ["legal_address.last_name", "", "Last Name is a required field"],
    ["legal_address.last_name", "  ", "Last Name is a required field"],
    ["legal_address.last_name", "Doe", null]
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
        await act(async () => {
          input.simulate("blur")
          await wait(10)
        })
        wrapper.update()
        assert.deepEqual(
          findFormikErrorByName(wrapper, name).text(),
          errorMessage
        )
      })
    }
  )
})
