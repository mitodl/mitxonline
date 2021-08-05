// @flow
import { assert } from "chai"
import sinon from "sinon"

import EditProfilePage, {
  EditProfilePage as InnerEditProfilePage
} from "./EditProfilePage"
import {
  makeAnonymousUser,
  makeCountries,
  makeUser
} from "../../../factories/user"
import IntegrationTestHelper from "../../../util/integration_test_helper"

describe("EditProfilePage", () => {
  let helper, renderPage
  const user = makeUser()
  const countries = makeCountries()

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    renderPage = helper.configureHOCRenderer(
      EditProfilePage,
      InnerEditProfilePage,
      {
        entities: {
          currentUser: user,
          countries:   countries
        }
      },
      {}
    )
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("renders the page for a logged in user", async () => {
    const { inner } = await renderPage()
    assert.isTrue(inner.find("EditProfileForm").exists())
  })

  //
  ;[[true, "with errors"], [false, "without errors"]].forEach(
    ([hasError, desc]) => {
      it(`handles form submission ${desc}`, async () => {
        const { inner } = await renderPage()
        const setSubmitting = helper.sandbox.stub()
        const setErrors = helper.sandbox.stub()
        const values = user
        const actions = {
          setErrors,
          setSubmitting
        }

        helper.handleRequestStub.returns({
          body: {
            errors: hasError ? "some errors" : null
          }
        })

        await inner.find("EditProfileForm").prop("onSubmit")(values, actions)
        sinon.assert.calledWith(
          helper.handleRequestStub,
          "/api/users/me",
          "PATCH",
          {
            body:        values,
            credentials: undefined,
            headers:     { "X-CSRFTOKEN": null }
          }
        )
        sinon.assert.calledWith(setSubmitting, false)
        if (hasError) {
          assert.isNull(helper.currentLocation)
          sinon.assert.calledOnce(setErrors)
        } else {
          assert.equal(helper.currentLocation.pathname, "/profile/")
          sinon.assert.notCalled(setErrors)
        }
      })
    }
  )
})
