// @flow
import { assert } from "chai"
import sinon from "sinon"

import CartPage, {
  CartPage as InnerCartPage,
  mapPropsToConfig
} from "./CartPage"
import IntegrationTestHelper from "../../../util/integration_test_helper"

describe("CartPage", () => {
  let helper, renderPage

  const anonymousUser = {
    id:               null,
    username:         "",
    email:            null,
    legal_address:    null,
    user_profile:     null,
    is_anonymous:     true,
    is_authenticated: false,
    is_staff:         false,
    is_superuser:     false,
    grants:           [],
    is_active:        false
  }

  const loggedInUser = {
    ...anonymousUser,
    id:               1,
    username:         "test",
    email:            "test@example.com",
    is_anonymous:     false,
    is_authenticated: true,
    is_active:        true
  }

  const cartItem = {
    product: {
      id:                 1,
      price:              "100.00",
      description:        "test product",
      purchasable_object: {
        course: {
          page: {
            financial_assistance_form_url: "https://example.com/fa"
          }
        }
      }
    }
  }

  beforeEach(() => {
    helper = new IntegrationTestHelper()

    renderPage = helper.configureShallowRenderer(CartPage, InnerCartPage, {
      entities: {
        cartItems:       [cartItem],
        totalPrice:      100,
        discountedPrice: 100,
        discounts:       [],
        currentUser:     loggedInUser
      },
      queries: {
        cartItems: {
          isPending: false
        }
      }
    })
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("shows the financial assistance offer link when the user is authenticated", async () => {
    const { inner } = await renderPage()
    assert.isOk(inner.instance().renderFinancialAssistanceOffer())
  })

  it("suppresses the financial assistance offer link when the user is logged out", async () => {
    const { inner } = await renderPage({
      entities: { currentUser: anonymousUser }
    })
    assert.isNull(inner.instance().renderFinancialAssistanceOffer())
  })

  it("passes isAuthenticated=true down to OrderSummaryCard when logged in", async () => {
    const { inner } = await renderPage()
    const summaryCard = inner.find("OrderSummaryCard")
    assert.isTrue(summaryCard.prop("isAuthenticated"))
  })

  it("passes isAuthenticated=false down to OrderSummaryCard when logged out", async () => {
    const { inner } = await renderPage({
      entities: { currentUser: anonymousUser }
    })
    const summaryCard = inner.find("OrderSummaryCard")
    assert.isFalse(summaryCard.prop("isAuthenticated"))
  })

  describe("compliance info gate", () => {
    let originalLocation

    const incompleteUser = {
      ...loggedInUser,
      legal_address: {
        country:          "US",
        state:            "US-MA",
        first_name:       "Test",
        last_name:        "User",
        street_address_1: "",
        city:             "",
        postal_code:      ""
      },
      user_profile:              { year_of_birth: 1990 },
      compliance_missing_fields: ["city", "postal_code", "street_address_1"]
    }

    beforeEach(() => {
      originalLocation = Object.getOwnPropertyDescriptor(window, "location")
      Object.defineProperty(window, "location", {
        writable:     true,
        configurable: true,
        value:        { href: "" }
      })
    })

    afterEach(() => {
      // $FlowFixMe - originalLocation is always defined for window.location
      Object.defineProperty(window, "location", originalLocation)
    })

    it("only loads countries when the profile modal may be needed", () => {
      const queryKeys = currentUser =>
        mapPropsToConfig({ currentUser }).map(config => config.queryKey)

      assert.include(queryKeys(incompleteUser), "countries")
      assert.notInclude(queryKeys(loggedInUser), "countries")
    })

    it("goes straight to checkout when nothing is missing", async () => {
      const { inner } = await renderPage()
      inner.find("OrderSummaryCard").prop("onCheckout")("/checkout/to_payment")

      assert.equal(window.location, "/checkout/to_payment")
      assert.isFalse(inner.find("Modal").prop("isOpen"))
    })

    it("asks for the missing profile fields before checkout", async () => {
      const { inner } = await renderPage({
        entities: { currentUser: incompleteUser }
      })
      inner.find("OrderSummaryCard").prop("onCheckout")("/checkout/to_payment")
      inner.update()

      assert.notEqual(window.location, "/checkout/to_payment")
      assert.isTrue(inner.find("Modal").prop("isOpen"))
      assert.isTrue(
        inner.find("AddlProfileFieldsForm").prop("requireComplianceFields")
      )
    })

    it("saves the legal address and then continues to checkout", async () => {
      const { inner } = await renderPage({
        entities: { currentUser: incompleteUser }
      })
      inner.find("OrderSummaryCard").prop("onCheckout")("/checkout/to_payment")
      const legalAddress = {
        ...incompleteUser.legal_address,
        street_address_1: "1 Main St",
        city:             "Cambridge",
        postal_code:      "02139"
      }
      const setSubmitting = sinon.stub()

      await inner.instance().saveProfile(
        {
          legal_address: legalAddress,
          user_profile:  { year_of_birth: 1990 }
        },
        { setSubmitting }
      )

      sinon.assert.calledWith(
        helper.handleRequestStub,
        "/api/v0/users/me",
        "PATCH",
        sinon.match({ body: { legal_address: legalAddress } })
      )
      const { body } = helper.handleRequestStub.lastCall.args[2]
      assert.notProperty(body, "user_profile")
      assert.equal(window.location, "/checkout/to_payment")
      sinon.assert.calledWith(setSubmitting, false)
    })

    it("sends year of birth when the form changed it", async () => {
      const { inner } = await renderPage({
        entities: { currentUser: incompleteUser }
      })
      inner.find("OrderSummaryCard").prop("onCheckout")("/checkout/to_payment")

      await inner.instance().saveProfile(
        {
          legal_address: incompleteUser.legal_address,
          user_profile:  { year_of_birth: "1985" }
        },
        { setSubmitting: sinon.stub(), setErrors: sinon.stub() }
      )

      const { body } = helper.handleRequestStub.lastCall.args[2]
      assert.deepEqual(body.user_profile, { year_of_birth: "1985" })
    })

    it("shows the server's field errors when the save is rejected", async () => {
      const fieldErrors = {
        legal_address: {
          city: ["Ensure this field has no more than 255 characters."]
        }
      }
      helper.handleRequestStub
        .withArgs("/api/v0/users/me", "PATCH")
        .returns({ status: 400, body: { errors: fieldErrors } })
      const { inner } = await renderPage({
        entities: { currentUser: incompleteUser }
      })
      inner.find("OrderSummaryCard").prop("onCheckout")("/checkout/to_payment")
      const setErrors = sinon.stub()

      await inner.instance().saveProfile(
        {
          legal_address: incompleteUser.legal_address,
          user_profile:  { year_of_birth: 1990 }
        },
        { setSubmitting: sinon.stub(), setErrors }
      )

      sinon.assert.calledWith(setErrors, fieldErrors)
      assert.notEqual(window.location, "/checkout/to_payment")
    })
  })
})
