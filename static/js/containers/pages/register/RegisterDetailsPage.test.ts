import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { makeRegisterAuthResponse } from "../../../factories/auth"
import {
  FLOW_REGISTER,
  STATE_ERROR,
  STATE_ERROR_TEMPORARY,
  STATE_REGISTER_DETAILS,
  STATE_USER_BLOCKED
} from "../../../lib/auth"
import { routes } from "../../../lib/urls"
import { AuthStates } from "../../../types/auth"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import RegisterDetailsPage from "./RegisterDetailsPage"

describe("RegisterDetailsPage", () => {
  const detailsData = {
    name:          "Sally",
    username:      "custom-username",
    password:      "password1",
    legal_address: {
      address: "main st"
    }
  }
  const partialToken = "partialTokenTestValue"
  const body = {
    flow:          FLOW_REGISTER,
    partial_token: partialToken,
    ...detailsData
  }

  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    setSubmittingStub: sinon.SinonStub,
    setErrorsStub: sinon.SinonStub,
    countriesStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    setSubmittingStub = helper.sandbox.stub()
    setErrorsStub = helper.sandbox.stub()
    helper.browserHistory.replace(`?partial_token=${partialToken}`)
    countriesStub = helper.mockGetRequest("/api/countries/", [])
    renderPage = helper.configureRenderer(RegisterDetailsPage)
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { wrapper } = await renderPage()
    expect(wrapper.find("RegisterDetailsForm").exists()).toBeTruthy()
    expect(countriesStub.calledOnceWith()).toBeTruthy()
  })

  it("handles onSubmit for an error response", async () => {
    const { wrapper } = await renderPage()
    const error = "error message"
    const fieldErrors = {
      name: error
    }
    helper.handleRequestStub.returns({
      body: makeRegisterAuthResponse({
        state:        STATE_ERROR,
        field_errors: fieldErrors
      })
    })
    const onSubmit = wrapper.find("RegisterDetailsForm").prop("onSubmit")
    await act(async () => {
      // @ts-ignore
      await onSubmit!(detailsData, {
        setSubmitting: setSubmittingStub,
        setErrors:     setErrorsStub
      })
    })
    sinon.assert.calledWith(
      helper.handleRequestStub,
      "/api/register/details/",
      "POST",
      {
        body,
        headers:     undefined,
        credentials: undefined
      }
    )
    expect(helper.browserHistory).toHaveLength(1)
    sinon.assert.calledWith(setErrorsStub, fieldErrors)
    sinon.assert.calledWith(setSubmittingStub, false)
  })
  ;([
    [STATE_ERROR_TEMPORARY, [], routes.register.error, ""],
    [STATE_ERROR, [], routes.register.error, ""], // cover the case with an error but no messages
    [
      STATE_USER_BLOCKED,
      ["error_code"],
      routes.register.denied,
      "?error=error_code"
    ],
    [STATE_USER_BLOCKED, [], routes.register.denied, ""]
  ] as [AuthStates, string[], string, string][]).forEach(
    ([state, errors, pathname, search]) => {
      it(`redirects to ${pathname} when it receives auth state ${state}`, async () => {
        const { wrapper } = await renderPage()
        const apiStub = helper.mockPostRequest(
          "/api/register/details/",
          makeRegisterAuthResponse({
            state,
            errors,
            partial_token: "new_partial_token"
          })
        )
        const onSubmit = wrapper.find("RegisterDetailsForm").prop("onSubmit")
        await act(async () => {
          // @ts-ignore
          await onSubmit!(detailsData, {
            setSubmitting: setSubmittingStub,
            setErrors:     setErrorsStub
          })
        })
        sinon.assert.calledWith(apiStub, "/api/register/details/", "POST", {
          body,
          headers:     undefined,
          credentials: undefined
        })
        expect(helper.browserHistory).toHaveLength(2)
        expect(helper.browserHistory.location).toMatchObject({
          pathname,
          search
        })

        if (state === STATE_ERROR) {
          sinon.assert.calledWith(setErrorsStub, {})
        } else {
          sinon.assert.notCalled(setErrorsStub)
        }

        sinon.assert.calledWith(setSubmittingStub, false)
      })
    }
  )

  it("shows field errors from the auth response if they exist", async () => {
    const { wrapper } = await renderPage()
    const apiStub = helper.mockPostRequest(
      "/api/register/details/",
      makeRegisterAuthResponse({
        state:        STATE_REGISTER_DETAILS,
        field_errors: {
          username: "Invalid"
        },
        partial_token: "new_partial_token"
      })
    )
    const onSubmit = wrapper.find("RegisterDetailsForm").prop("onSubmit")
    await act(async () => {
      // @ts-ignore
      await onSubmit!(detailsData, {
        setSubmitting: setSubmittingStub,
        setErrors:     setErrorsStub
      })
    })
    sinon.assert.calledWith(apiStub, "/api/register/details/", "POST", {
      body,
      headers:     undefined,
      credentials: undefined
    })
    sinon.assert.calledOnceWithExactly(setErrorsStub, {
      username: "Invalid"
    })
  })
})
