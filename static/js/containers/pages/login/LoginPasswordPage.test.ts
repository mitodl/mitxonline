import { assert } from "chai"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { makeLoginAuthResponse } from "../../../factories/auth"
import {
  STATE_ERROR,
  STATE_LOGIN_PASSWORD,
  STATE_SUCCESS
} from "../../../lib/auth"
import { AuthResponse } from "../../../types/auth"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import LoginPasswordPage from "./LoginPasswordPage"

describe("LoginPasswordPage", () => {
  const password = "abc123"
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    setSubmittingStub: sinon.SinonStub,
    setErrorsStub: sinon.SinonStub,
    auth: AuthResponse

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    setSubmittingStub = helper.sandbox.stub()
    setErrorsStub = helper.sandbox.stub()
    auth = makeLoginAuthResponse({
      state: STATE_LOGIN_PASSWORD
    })
    renderPage = helper.configureRenderer(
      LoginPasswordPage,
      {},
      {
        entities: {
          auth
        }
      }
    )
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { wrapper } = await renderPage()
    assert.ok(wrapper.find("LoginPasswordForm").exists())
  })

  it("handles onSubmit for an error response", async () => {
    const { wrapper } = await renderPage()
    const fieldErrors = {
      email: "error message"
    }
    helper.mockPostRequest(
      "/api/login/password/",
      makeLoginAuthResponse({
        state:        STATE_ERROR,
        field_errors: fieldErrors
      })
    )
    const onSubmit = wrapper.find("LoginPasswordForm").prop("onSubmit")
    await act(async () => {
      await onSubmit!(
        {
          password
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub,
          setErrors:     setErrorsStub
        }
      )
      wrapper.update()
    })
    assert.lengthOf(helper.browserHistory, 1)
    sinon.assert.calledWith(setErrorsStub, fieldErrors)
    sinon.assert.calledWith(setSubmittingStub, false)
  })

  it("handles onSubmit success", async () => {
    const { wrapper } = await renderPage()
    helper.mockPostRequest(
      "/api/login/password/",
      makeLoginAuthResponse({
        state: STATE_SUCCESS
      })
    )
    const onSubmit = wrapper.find("LoginPasswordForm").prop("onSubmit")

    await act(async () => {
      await onSubmit!(
        {
          password
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub,
          setErrors:     setErrorsStub
        }
      )
      wrapper.update()
    })
    expect(window.location).toBeAt("/dashboard/")
    sinon.assert.notCalled(setErrorsStub)
    sinon.assert.calledWith(setSubmittingStub, false)
  })
})
