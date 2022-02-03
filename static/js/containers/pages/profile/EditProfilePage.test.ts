import { assert } from "chai"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { makeCountries, makeUser } from "../../../factories/user"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import EditProfilePage from "./EditProfilePage"

describe("EditProfilePage", () => {
  let helper: IntegrationTestHelper, renderPage: TestRenderer
  const user = makeUser()
  const countries = makeCountries()

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    helper.mockGetRequest("/api/countries/", countries)
    helper.mockGetRequest("/api/user/me/", user)
    renderPage = helper.configureRenderer(
      EditProfilePage,
      {},
      {
        entities: {
          currentUser: user
        }
      }
    )
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("renders the page for a logged in user", async () => {
    const { wrapper } = await renderPage()
    assert.isTrue(wrapper.find("EditProfileForm").exists())
  })
  ;[
    [true, "with errors"],
    [false, "without errors"]
  ].forEach(([hasError, desc]) => {
    it(`handles form submission ${desc}`, async () => {
      const { wrapper } = await renderPage()
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
      const onSubmit = wrapper.find("EditProfileForm").prop("onSubmit")
      await act(async () => {
        // @ts-ignore
        await onSubmit!(values, actions)
      })
      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/users/me",
        "PATCH",
        {
          body:        values,
          credentials: undefined,
          headers:     {
            "X-CSRFTOKEN": ""
          }
        }
      )
      sinon.assert.calledWith(setSubmitting, false)

      if (hasError) {
        assert.isNull(helper.currentLocation)
        sinon.assert.calledOnce(setErrors)
      } else {
        assert.equal(helper.currentLocation?.pathname, "/profile/")
        sinon.assert.notCalled(setErrors)
      }
    })
  })
})
