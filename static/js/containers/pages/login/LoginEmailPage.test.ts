import { assert } from "chai"
import { act } from "react-dom/test-utils"
import sinon from "sinon"
import { makeLoginAuthResponse } from "../../../factories/auth"
import {
  STATE_ERROR,
  STATE_LOGIN_PASSWORD,
  STATE_REGISTER_REQUIRED
} from "../../../lib/auth"
import { routes } from "../../../lib/urls"
import { AuthStates } from "../../../types/auth"
import IntegrationTestHelper, {
  TestRenderer
} from "../../../util/integration_test_helper"
import LoginEmailPage from "./LoginEmailPage"

describe("LoginEmailPage", () => {
  const email = "email@example.com"
  let helper: IntegrationTestHelper,
    renderPage: TestRenderer,
    setSubmittingStub: sinon.SinonStub,
    setErrorsStub: sinon.SinonStub

  beforeEach(() => {
    helper = new IntegrationTestHelper()
    setSubmittingStub = helper.sandbox.stub()
    setErrorsStub = helper.sandbox.stub()
    helper.browserHistory.push("?next=/checkout/product=1")
    renderPage = helper.configureRenderer(LoginEmailPage)
  })
  afterEach(() => {
    helper.cleanup()
  })

  it("displays a form", async () => {
    const { wrapper } = await renderPage()
    assert.ok(wrapper.find("EmailForm").exists())
  })

  it("next query parameter exists in create account link", async () => {
    const { wrapper } = await renderPage()
    assert.ok(
      wrapper
        .find(`Link[to='${routes.register.begin}?next=/checkout/product=1']`)
        .exists()
    )
  })
  ;([STATE_ERROR, STATE_REGISTER_REQUIRED] as AuthStates[]).forEach(state => {
    it(`handles onSubmit by calling setErrors given state=${state}`, async () => {
      const { wrapper } = await renderPage()
      const fieldErrors = {
        email: "error message"
      }
      helper.handleRequestStub.returns({
        body: makeLoginAuthResponse({
          state,
          field_errors: fieldErrors
        })
      })
      const onSubmit = wrapper.find("EmailForm").prop("onSubmit")

      await act(async () => {
        await onSubmit!(
          {
            email
          },
          // @ts-ignore
          {
            setSubmitting: setSubmittingStub,
            setErrors:     setErrorsStub
          }
        )
      })

      assert.lengthOf(helper.browserHistory, 2)
      sinon.assert.calledWith(setErrorsStub, fieldErrors)
      sinon.assert.calledWith(setSubmittingStub, false)
    })
  })

  it("handles onSubmit for an existing user password login", async () => {
    const { wrapper } = await renderPage()
    helper.handleRequestStub.returns({
      body: makeLoginAuthResponse({
        state: STATE_LOGIN_PASSWORD
      })
    })
    const onSubmit = wrapper.find("EmailForm").prop("onSubmit")

    await act(async () => {
      await onSubmit!(
        {
          email
        },
        // @ts-ignore
        {
          setSubmitting: setSubmittingStub,
          setErrors:     setErrorsStub
        }
      )
    })

    assert.lengthOf(helper.browserHistory, 3)
    assert.include(helper.browserHistory.location, {
      pathname: routes.login.password,
      search:   ""
    })
    sinon.assert.notCalled(setErrorsStub)
    sinon.assert.calledWith(setSubmittingStub, false)
  })
})
