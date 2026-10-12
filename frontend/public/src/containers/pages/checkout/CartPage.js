// @flow
/* global SETTINGS: false */
import React from "react"
import DocumentTitle from "react-document-title"
import { CART_DISPLAY_PAGE_TITLE } from "../../../constants"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
// $FlowFixMe
import { Modal, ModalBody, ModalHeader } from "reactstrap"

import type { BasketItem, Discount } from "../../../flow/cartTypes"
import type { Country, CurrentUser } from "../../../flow/authTypes"

import Loader from "../../../components/Loader"
import { CartItemCard } from "../../../components/CartItemCard"
import { OrderSummaryCard } from "../../../components/OrderSummaryCard"
import AddlProfileFieldsForm from "../../../components/forms/AddlProfileFieldsForm"
import { needsComplianceInfo } from "../../../components/forms/ProfileFormFields"

import {
  cartQuery,
  cartQueryKey,
  cartSelector,
  totalPriceSelector,
  discountedPriceSelector,
  discountSelector,
  applyDiscountCodeMutation
} from "../../../lib/queries/cart"
import users, { currentUserSelector } from "../../../lib/queries/users"

import type { RouterHistory } from "react-router"
import { isSuccessResponse } from "../../../lib/util"
import { addUserNotification } from "../../../actions"

type Props = {
  history: RouterHistory,
  cartItems: Array<BasketItem>,
  totalPrice: number,
  discountedPrice: number,
  discounts: Array<Discount>,
  isLoading: boolean,
  applyDiscountCode: (code: string) => Promise<any>,
  addUserNotification: Function,
  forceRequest: Function,
  currentUser: ?CurrentUser,
  countries: Array<Country>,
  updateProfile: (profileData: Object) => Promise<any>
}

type CartState = {
  discountCode: string,
  checkoutUrl: string
}

export class CartPage extends React.Component<Props, CartState> {
  state = {
    discountCode: "",
    checkoutUrl:  ""
  }

  handleCheckout(checkoutUrl: string) {
    if (needsComplianceInfo(this.props.currentUser)) {
      this.setState({ checkoutUrl })
    } else {
      window.location = checkoutUrl
    }
  }

  async saveProfile(values: Object, { setSubmitting, setErrors }: Object) {
    const { currentUser, updateProfile } = this.props
    const currentYearOfBirth = pathOr(
      null,
      ["user_profile", "year_of_birth"],
      currentUser
    )
    const profileData: Object = { legal_address: values.legal_address }
    // The user serializer resets addl_field_flag whenever user_profile is
    // sent, so only include it when the form actually changed it.
    if (
      String(values.user_profile.year_of_birth) !== String(currentYearOfBirth)
    ) {
      profileData.user_profile = {
        year_of_birth: values.user_profile.year_of_birth
      }
    }

    try {
      const resp = await updateProfile(profileData)
      if (isSuccessResponse(resp)) {
        window.location = this.state.checkoutUrl
      } else if (resp.body && resp.body.errors) {
        // e.g. {errors: {legal_address: {city: ["..."]}}}
        setErrors(resp.body.errors)
      }
    } finally {
      setSubmitting(false)
    }
  }

  renderComplianceInfoModal() {
    const { currentUser, countries } = this.props
    const { checkoutUrl } = this.state

    if (!currentUser || !currentUser.is_authenticated) {
      return null
    }

    return (
      <Modal
        id="compliance-info-dialog"
        className="upgrade-enrollment-modal"
        isOpen={Boolean(checkoutUrl)}
        toggle={() => this.setState({ checkoutUrl: "" })}
      >
        <ModalHeader toggle={() => this.setState({ checkoutUrl: "" })}>
          Provide More Info
        </ModalHeader>
        <ModalBody>
          <p>
            We need a few more details about you before you can place your
            order.
          </p>
          <AddlProfileFieldsForm
            onSubmit={this.saveProfile.bind(this)}
            user={currentUser}
            countries={countries}
            requireComplianceFields={true}
          />
        </ModalBody>
      </Modal>
    )
  }

  async addDiscount(ev: Object, { setErrors }: any) {
    const subbedCode = String(ev.couponCode || "").trim()
    const { applyDiscountCode, forceRequest } = this.props

    if (!subbedCode) {
      return
    }

    this.setState({ discountCode: subbedCode })

    const resp = await applyDiscountCode(subbedCode)

    if (isSuccessResponse(resp)) {
      // Discount successfully applied, re-fetch cart
      forceRequest()
    } else {
      // Show error in the input field
      setErrors({
        couponCode: `Discount code ${subbedCode} is invalid.`
      })
    }
  }
  renderCartItemCard(cartItem: BasketItem) {
    return (
      <CartItemCard
        key={`cartsummarycard_${cartItem.product.id}`}
        product={cartItem.product}
      />
    )
  }

  renderEmptyCartCard() {
    return (
      <div
        className="enrolled-item container card mb-4 rounded-0 flex-grow-1"
        key="cartsummarycard"
      >
        <div className="row d-flex flex-sm-columm p-md-3">
          <div className="flex-grow-1 mx-3 d-sm-flex flex-column">
            <div className="detail">Your cart is empty.</div>
          </div>
        </div>
      </div>
    )
  }

  renderOrderSummaryCard() {
    const { totalPrice, discountedPrice, discounts, currentUser } = this.props
    const refunds = []

    return (
      <OrderSummaryCard
        totalPrice={totalPrice}
        orderFulfilled={false}
        discountedPrice={discountedPrice}
        discounts={discounts}
        refunds={refunds}
        addDiscount={this.addDiscount.bind(this)}
        discountCode={this.state.discountCode}
        isAuthenticated={Boolean(currentUser && currentUser.is_authenticated)}
        onCheckout={this.handleCheckout.bind(this)}
      />
    )
  }

  renderFinancialAssistanceOffer() {
    const { cartItems, discounts, currentUser } = this.props

    if (!currentUser || !currentUser.is_authenticated) {
      return null
    }

    let userFlexiblePriceExists = false
    // Check if there are any discounts, and if those discounts are for flexible pricing.
    if (
      discounts &&
      discounts.length > 0 &&
      typeof discounts.find(
        discount => discount.payment_type === "financial-assistance"
      ) !== "undefined"
    ) {
      userFlexiblePriceExists = true
    }

    if (
      cartItems &&
      cartItems.length > 0 &&
      userFlexiblePriceExists === false
    ) {
      const purchasableObject =
        cartItems[0].product && cartItems[0].product.purchasable_object
      const financialAssistanceUrl =
        purchasableObject &&
        purchasableObject.course &&
        purchasableObject.course.page &&
        purchasableObject.course.page.financial_assistance_form_url

      if (financialAssistanceUrl) {
        return <a href={financialAssistanceUrl}>Need financial assistance?</a>
      }
    }
  }

  render() {
    const { cartItems, isLoading } = this.props

    return (
      <DocumentTitle
        title={`${SETTINGS.site_name} | ${CART_DISPLAY_PAGE_TITLE}`}
      >
        <Loader isLoading={isLoading}>
          <div role="banner" className="std-page-header">
            <h1>{CART_DISPLAY_PAGE_TITLE}</h1>
          </div>
          <div className="std-page-body cart container">
            <div className="row d-flex flex-column-reverse flex-md-column flex-lg-row">
              <div className="col-lg-8 enrolled-items">
                <p className="purchase-block-intro">
                  You are about to purchase the following:
                </p>
                {cartItems && cartItems.length > 0 ?
                  cartItems.map(this.renderCartItemCard.bind(this)) :
                  this.renderEmptyCartCard()}
              </div>
              <div className="col-lg-4 summary-cards">
                <div className="d-md-flex cart-helptext">
                  <div>{this.renderFinancialAssistanceOffer()}</div>
                  <div className="text-right ms-auto">
                    <a
                      href="https://support.learn.mit.edu/"
                      target="_blank"
                      rel="noreferrer"
                    >
                      Help &amp; FAQs
                    </a>
                  </div>
                </div>
                {this.renderOrderSummaryCard()}
              </div>
            </div>
            {this.renderComplianceInfoModal()}
          </div>
        </Loader>
      </DocumentTitle>
    )
  }
}

const applyDiscountCode = (code: string) =>
  mutateAsync(applyDiscountCodeMutation(code))

const updateProfile = (profileData: Object) =>
  mutateAsync(users.editProfileMutation(profileData))

const mapStateToProps = createStructuredSelector({
  cartItems:       cartSelector,
  totalPrice:      totalPriceSelector,
  discountedPrice: discountedPriceSelector,
  discounts:       discountSelector,
  isLoading:       pathOr(true, ["queries", cartQueryKey, "isPending"]),
  currentUser:     currentUserSelector,
  countries:       users.countriesSelector
})

const mapDispatchToProps = {
  addUserNotification,
  applyDiscountCode,
  updateProfile
}

const mapPropsToConfig = () => [cartQuery(), users.countriesQuery()]

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(CartPage)
