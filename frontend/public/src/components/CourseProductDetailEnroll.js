// @flow
import React, { Fragment } from "react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { mutateAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
// $FlowFixMe
import { Modal, ModalBody, ModalHeader } from "reactstrap"

import Loader from "./Loader"
import { routes } from "../lib/urls"
import {
  getFlexiblePriceForProduct,
  formatLocalePrice,
  checkFeatureFlag,
  isSuccessResponse
} from "../lib/util"
import { EnrollmentFlaggedCourseRun } from "../flow/courseTypes"
import {
  coursesSelector,
  coursesQuery,
  coursesQueryKey
} from "../lib/queries/courseRuns"

import { formatPrettyDate, emptyOrNil } from "../lib/util"
import moment from "moment-timezone"
import { getFirstRelevantRun } from "../lib/courseApi"
import { getCSRFCookie } from "../lib/api"
import users, { currentUserSelector } from "../lib/queries/users"
import {
  enrollmentMutation,
  deactivateEnrollmentMutation
} from "../lib/queries/enrollment"
import AddlProfileFieldsForm from "./forms/AddlProfileFieldsForm"
import CourseInfoBox from "./CourseInfoBox"

import type { User, Country } from "../flow/authTypes"
import type { Product } from "../flow/cartTypes"
import { addUserNotification } from "../actions"
import { applyCartMutation } from "../lib/queries/cart"
import queries from "../lib/queries"

type Props = {
  courseId: ?string,
  isLoading: ?boolean,
  courses: ?Array<any>,
  status: ?number,
  courseIsLoading: ?boolean,
  courseStatus: ?number,
  upgradeEnrollmentDialogVisibility: boolean,
  addProductToBasket: (user: number, productId: number) => Promise<any>,
  currentUser: User,
  createEnrollment: (runId: number) => Promise<any>,
  addToCart: (productId: string) => Promise<any>,
  deactivateEnrollment: (runId: number) => Promise<any>,
  updateAddlFields: (currentUser: User) => Promise<any>,
  forceRequest: () => any,
  countries: Array<Country>
}
type ProductDetailState = {
  upgradeEnrollmentDialogVisibility: boolean,
  addedToCartDialogVisibility: boolean,
  showAddlProfileFieldsModal: boolean,
  currentCourseRun: ?EnrollmentFlaggedCourseRun,
  destinationUrl: string
}

export class CourseProductDetailEnroll extends React.Component<
  Props,
  ProductDetailState
> {
  state = {
    upgradeEnrollmentDialogVisibility: false,
    addedToCartDialogVisibility:       false,
    currentCourseRun:                  null,
    showAddlProfileFieldsModal:        false,
    destinationUrl:                    ""
  }

  toggleAddlProfileFieldsModal() {
    this.setState({
      showAddlProfileFieldsModal: !this.state.showAddlProfileFieldsModal
    })

    if (
      !this.state.showAddlProfileFieldsModal &&
      this.state.destinationUrl.length > 0
    ) {
      const target = this.state.destinationUrl
      this.setState({
        destinationUrl: ""
      })
      window.open(target, "_blank")
    }
  }
  toggleCartConfirmationDialogVisibility() {
    this.setState({
      addedToCartDialogVisibility: !this.state.addedToCartDialogVisibility
    })
  }

  async onAddToCartClick() {
    const { addToCart } = this.props
    const run = this.getCurrentCourseRun()
    if (run && run.products) {
      const product = run.products[0]
      const addToCartResponse = await addToCart(product.id)
      this.setState({
        upgradeEnrollmentDialogVisibility: false
      })
      if (isSuccessResponse(addToCartResponse)) {
        this.setState({
          addedToCartDialogVisibility: true
        })
      } else {
        // set notification something went wrong
      }
    }
  }

  redirectToCourseHomepage(url: string, ev: any) {
    /*
    If we've got addl_field_flag, then display the extra info modal. Otherwise,
    send the learner directly to the page.
    */

    const { currentUser, updateAddlFields } = this.props
    if (
      currentUser &&
      currentUser.legal_address &&
      currentUser.legal_address.country !== "" &&
      currentUser.legal_address.country !== null &&
      currentUser.user_profile &&
      currentUser.user_profile.year_of_birth !== "" &&
      currentUser.user_profile.year_of_birth !== null
    ) {
      return
    }

    ev.preventDefault()

    this.setState({
      destinationUrl:             url,
      showAddlProfileFieldsModal: true
    })

    updateAddlFields(currentUser)
  }

  async saveProfile(profileData: User, { setSubmitting }: Object) {
    const { updateAddlFields } = this.props

    try {
      await updateAddlFields(profileData)
    } finally {
      setSubmitting(false)
      this.toggleAddlProfileFieldsModal()
    }
  }
  toggleUpgradeDialogVisibility = () => {
    const { upgradeEnrollmentDialogVisibility } = this.state
    this.setCurrentCourseRun(null)
    this.setState({
      upgradeEnrollmentDialogVisibility: !upgradeEnrollmentDialogVisibility
    })
  }

  setCurrentCourseRun = (courseRun: EnrollmentFlaggedCourseRun) => {
    this.setState({
      currentCourseRun: courseRun
    })
  }

  hndSetCourseRun = (event: any) => {
    const { courses } = this.props
    const courseRuns = courses && courses[0] ? courses[0].courseruns : null
    if (event.target.value === "default") {
      this.setCurrentCourseRun(null)
      return
    }
    const matchingCourseRun =
      courseRuns &&
      courseRuns.find(
        (elem: EnrollmentFlaggedCourseRun) =>
          elem.id === parseInt(event.target.value)
      )
    if (matchingCourseRun) {
      this.setCurrentCourseRun(matchingCourseRun)
    }
  }

  getCurrentCourseRun = (): EnrollmentFlaggedCourseRun => {
    return this.state.currentCourseRun
  }

  cancelEnrollment() {
    const { upgradeEnrollmentDialogVisibility } = this.state

    this.setState({
      upgradeEnrollmentDialogVisibility: !upgradeEnrollmentDialogVisibility
    })
  }

  renderRunSelectorButtons(
    enrollableCourseRuns: Array<EnrollmentFlaggedCourseRun>
  ) {
    return (
      <>
        {enrollableCourseRuns && enrollableCourseRuns.length > 1 ? (
          <label htmlFor="choose-courserun">Choose a date:</label>
        ) : (
          <label htmlFor="choose-courserun">
            There is one session available:
          </label>
        )}
        <select
          onChange={this.hndSetCourseRun.bind(this)}
          className="form-control"
        >
          <option value="default" key="default-select">
            Please Select
          </option>
          {enrollableCourseRuns &&
            enrollableCourseRuns.map((elem: EnrollmentFlaggedCourseRun) => (
              <option value={elem.id} key={`courserun-selection-${elem.id}`}>
                {formatPrettyDate(moment(new Date(elem.start_date)))} -{" "}
                {formatPrettyDate(moment(new Date(elem.end_date)))}{" "}
                {elem.is_upgradable ? "" : "(no certificate available)"}
              </option>
            ))}
        </select>
      </>
    )
  }

  getEnrollmentForm(run: EnrollmentFlaggedCourseRun) {
    const csrfToken = getCSRFCookie()

    return (
      <form action="/enrollments/" method="post">
        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
        <input type="hidden" name="run" value={run ? run.id : ""} />
        <button
          type="submit"
          className="btn enroll-now enroll-now-free btn-gradient-white-to-blue"
          disabled={!run || !run.is_enrollable}
        >
          Enroll for <strong>Free without a certificate</strong>
        </button>
      </form>
    )
  }

  updateDate(run: EnrollmentFlaggedCourseRun) {
    // for original design - not used in course infobox design
    let date = emptyOrNil(run.start_date) ?
      undefined :
      moment(new Date(run.start_date))
    date = date ? date.utc() : date
    const dateElem = document.getElementById("start_date")
    if (dateElem) {
      dateElem.innerHTML = `<strong>${formatPrettyDate(date)}</strong>`
    }
  }

  renderAddToCartConfirmationDialog() {
    const { courses } = this.props
    const { addedToCartDialogVisibility } = this.state
    const course = courses && courses[0] ? courses[0] : null
    return (
      <Modal
        id={`added-to-cart-dialog`}
        className="added-to-cart-modal"
        isOpen={addedToCartDialogVisibility}
        toggle={() => this.toggleCartConfirmationDialogVisibility()}
        centered
      >
        <ModalHeader
          toggle={() => this.toggleCartConfirmationDialogVisibility()}
        >
          Added to Cart
        </ModalHeader>
        <ModalBody>
          <div className="green-label">
            <img
              className="green-check-circle-icon"
              src="/static/images/check_circle.svg"
              alt="Check"
            />
            <strong>{course && course.title}</strong> added to your cart.
          </div>
          <div className="float-container">
            <button 
              className="btn btn-gradient-white-to-blue btn-secondary close-dialog-btn"
              onClick={() => this.toggleCartConfirmationDialogVisibility()}
            >
              Close
            </button>
            <button
              type="submit"
              onClick={() => (window.location = routes.cart)}
              className="btn btn-gradient-red-to-blue btn-secondary"
            >
              <div className="go-to-cart-btn-text">
                <strong>Go to Cart</strong>
                <img
                  className="right-arrow-icon"
                  src="/static/images/arrow-right-line.svg"
                />
              </div>
            </button>
          </div>
        </ModalBody>
      </Modal>
    )
  }

  renderUpgradeEnrollmentDialog() {
    const { courses, currentUser } = this.props
    const courseRuns = courses && courses[0] ? courses[0].courseruns : null
    const enrollableCourseRuns = courseRuns ?
      courseRuns.filter(
        (run: EnrollmentFlaggedCourseRun) => run.is_enrollable
      ) :
      []
    const upgradableCourseRuns = enrollableCourseRuns.filter(
      (run: EnrollmentFlaggedCourseRun) => run.is_upgradable
    )
    if (upgradableCourseRuns.length < 1 && enrollableCourseRuns.length < 1) {
      return null
    }
    const course = courses && courses[0] ? courses[0] : null
    const run = this.getCurrentCourseRun()
    const needFinancialAssistanceLink =
      run &&
      course &&
      course.page &&
      course.page.financial_assistance_form_url &&
      !run.approved_flexible_price_exists ? (
          <a
            href={
              course && course.page && course.page.financial_assistance_form_url
            }
            className="finaid-link financial-assistance-link"
          >
          Need financial assistance?
          </a>
        ) : null
    const { upgradeEnrollmentDialogVisibility } = this.state
    const product = run && run.products ? run.products[0] : null
    const newCartDesign = checkFeatureFlag(
      "new-cart-design",
      currentUser && currentUser.id ? currentUser.id : "anonymousUser"
    )
    const canUpgrade = !!(run && run.is_upgradable && product)
    return upgradableCourseRuns.length > 0 ||
      enrollableCourseRuns.length > 1 ? (
        <Modal
          id={`upgrade-enrollment-dialog`}
          className="upgrade-enrollment-modal"
          isOpen={upgradeEnrollmentDialogVisibility}
          toggle={() => this.cancelEnrollment()}
          centered
        >
          <ModalHeader toggle={() => this.cancelEnrollment()}>
            {course && course.title}
          </ModalHeader>
          <ModalBody>
            {enrollableCourseRuns.length > 0 ? (
              <div className="row date-selector-button-bar">
                <div className="col-12">
                  <div>{this.renderRunSelectorButtons(enrollableCourseRuns)}</div>
                </div>
              </div>
            ) : null}

            {upgradableCourseRuns.length > 0 ? (
              <>
                <div className="row upsell-messaging-header">
                  <div className="col-12 p-0 font-weight-bold">
                  Do you want to earn a certificate?
                  </div>
                </div>
                <div className="row d-sm-flex flex-md-row flex-sm-column">
                  <div className="col-md-6 col-sm-12">
                    <ul>
                      <li> Certificate is signed by MIT faculty</li>
                      <li>
                        {" "}
                      Demonstrates knowledge and skills taught in this course
                      </li>
                      <li> Enhance your college &amp; earn a promotion</li>
                    </ul>
                  </div>
                  <div className="col-md-6 col-sm-12">
                    <ul>
                      <li>Highlight on your resume/CV</li>
                      <li>Share on your social channels &amp; LinkedIn</li>
                      <li>
                      Enhance your college application with an earned
                      certificate from MIT
                      </li>
                    </ul>
                  </div>
                </div>
                <div className="row certificate-pricing-row d-sm-flex flex-md-row flex-sm-column">
                  <div
                    className={`col-md-6 col-sm-12 certificate-pricing d-flex align-items-center ${
                      run ? "" : "opacity-50"
                    }`}
                  >
                    <div className="certificate-pricing-logo">
                      <img src="/static/images/certificates/certificate-logo.svg" />
                    </div>
                    <p>
                      <strong> Certificate track: </strong>
                      <span id="certificate-price-info">
                        {product &&
                        run.is_upgradable &&
                        formatLocalePrice(getFlexiblePriceForProduct(product))}
                      </span>
                      <>
                        <br />
                        {canUpgrade ? (
                          <>
                            <span className="text-danger">
                            Payment due:{" "}
                              {formatPrettyDate(moment(run.upgrade_deadline))}
                            </span>
                            {needFinancialAssistanceLink}
                          </>
                        ) : (
                          <strong id="certificate-price-info">
                          not available
                          </strong>
                        )}
                      </>
                    </p>
                  </div>
                  {newCartDesign ? (
                    <div className="col-md-6 col-sm-12 pr-0">
                      <div className="new-design">
                        <button
                          onClick={this.onAddToCartClick.bind(this)}
                          type="button"
                          className="btn btn-upgrade btn-gradient-red-to-blue"
                          disabled={!canUpgrade}
                        >
                          <i className="shopping-cart-line-icon" />
                          <div className="upgrade-btn-text">
                            <strong>Add to Cart</strong>
                            <br />
                            <span>to get a Certificate</span>
                          </div>
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="col-md-6 col-sm-12 pr-0">
                      <form
                        action="/cart/add/"
                        method="get"
                        className="text-center"
                      >
                        <input
                          type="hidden"
                          name="product_id"
                          value={(product && product.id) || ""}
                        />
                        <button
                          type="submit"
                          className="btn btn-upgrade btn-gradient-red-to-blue"
                          disabled={!canUpgrade}
                        >
                          <div className="upgrade-btn-text">
                            <strong>Add to Cart</strong>
                            <br />
                            <span>to get a Certificate</span>
                          </div>
                        </button>
                      </form>
                    </div>
                  )}
                </div>
              </>
            ) : null}
            <div className="row upgrade-options-row">
              <div>{this.getEnrollmentForm(run)}</div>
            </div>
          </ModalBody>
        </Modal>
      ) : null
  }

  renderAddlProfileFieldsModal() {
    const { currentUser, countries } = this.props
    const { showAddlProfileFieldsModal } = this.state

    return (
      <Modal
        id={`upgrade-enrollment-dialog`}
        className="upgrade-enrollment-modal"
        isOpen={showAddlProfileFieldsModal}
        toggle={() => this.toggleAddlProfileFieldsModal()}
      >
        <ModalHeader
          id={`more-info-modal-${currentUser.id}`}
          toggle={() => this.toggleAddlProfileFieldsModal()}
        >
          Provide More Info
        </ModalHeader>
        <ModalBody>
          <div className="row">
            <div className="col-12">
              <p>
                We need more information about you before you can start the
                course.
              </p>
            </div>
          </div>
          <AddlProfileFieldsForm
            onSubmit={this.saveProfile.bind(this)}
            onCancel={() => this.toggleAddlProfileFieldsModal()}
            user={currentUser}
            countries={countries}
          ></AddlProfileFieldsForm>
        </ModalBody>
      </Modal>
    )
  }

  renderEnrollLoginButton(run: EnrollmentFlaggedCourseRun) {
    return (
      <h2>
        <a
          href={`${routes.apiGatewayLogin}?next=${encodeURIComponent(
            window.location.pathname
          )}`}
          className="btn btn-primary btn-enrollment-button btn-lg  btn-gradient-red-to-blue highlight"
        >
          {run.is_archived ? "Access Course Materials" : "Enroll Now"}
        </a>
      </h2>
    )
  }

  renderAccessCourseButton() {
    return (
      <h2>
        <button
          onClick={() =>
            (window.location = `${
              routes.apiGatewayLogin
            }?next=${encodeURIComponent(window.location.pathname)}`)
          }
          className="btn btn-primary btn-enrollment-button btn-lg highlight"
          disabled={true}
        >
          Access Course Materials
        </button>
      </h2>
    )
  }

  renderEnrollNowButton(
    run: EnrollmentFlaggedCourseRun,
    hasMultipleEnrollableRuns: boolean,
    product: Product | null
  ) {
    const csrfToken = getCSRFCookie()
    return run ? (
      <h2>
        {(product && run.is_upgradable) || hasMultipleEnrollableRuns ? (
          <button
            id="upgradeEnrollBtn"
            className="btn btn-primary btn-enrollment-button btn-lg btn-gradient-red-to-blue highlight enroll-now"
            onClick={() => this.toggleUpgradeDialogVisibility()}
            disabled={!run.is_enrollable}
          >
            Enroll now
          </button>
        ) : (
          <form action="/enrollments/" method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
            <input type="hidden" name="run" value={run ? run.id : ""} />
            <button
              type="submit"
              className="btn btn-primary btn-enrollment-button btn-gradient-red-to-blue highlight enroll-now"
              disabled={!run.is_enrollable}
            >
              {run.is_archived ? "Access Course Materials" : "Enroll Now"}
            </button>
          </form>
        )}
      </h2>
    ) : null
  }

  render() {
    const { courses, courseIsLoading, currentUser } = this.props
    let run,
      product = null
    const courseRuns = courses && courses[0] ? courses[0].courseruns : null
    const enrollableCourseRuns = courseRuns ?
      courseRuns.filter(
        (run: EnrollmentFlaggedCourseRun) => run.is_enrollable
      ) :
      []
    if (courses && courseRuns) {
      run = getFirstRelevantRun(courses[0], courseRuns)

      if (run) {
        product = run && run.products ? run.products[0] : null
        this.updateDate(run)
      }
    }
    const hasMultipleEnrollableRuns =
      enrollableCourseRuns && enrollableCourseRuns.length > 1

    return (
      <>
        {
          // $FlowFixMe: isLoading null or undefined
          <Loader
            key="product_detail_enroll_loader"
            isLoading={courseIsLoading}
          >
            <>
              {run ?
                currentUser && currentUser.id ?
                  this.renderEnrollNowButton(
                    run,
                    hasMultipleEnrollableRuns,
                    product
                  ) :
                  this.renderEnrollLoginButton(run) :
                this.renderAccessCourseButton()}

              {run && currentUser ? this.renderAddlProfileFieldsModal() : null}
              {this.renderUpgradeEnrollmentDialog()}
              {this.renderAddToCartConfirmationDialog()}
            </>
          </Loader>
        }
        <>
          {
            // $FlowFixMe: isLoading null or undefined
            <Loader key="course_info_loader" isLoading={courseIsLoading}>
              <CourseInfoBox
                courses={courses}
                currentUser={currentUser}
                enrollableCourseRuns={enrollableCourseRuns}
                setCurrentCourseRun={this.setCurrentCourseRun}
              ></CourseInfoBox>
            </Loader>
          }
        </>
      </>
    )
  }
}

const createEnrollment = (run: EnrollmentFlaggedCourseRun) =>
  mutateAsync(enrollmentMutation(run.id))

const addToCart = (productId: string) =>
  mutateAsync(applyCartMutation(productId))

const deactivateEnrollment = (run: number) =>
  mutateAsync(deactivateEnrollmentMutation(run))

const updateAddlFields = (currentUser: User) => {
  const updatedUser = {
    name:          currentUser.name,
    email:         currentUser.email,
    legal_address: currentUser.legal_address,
    user_profile:  {
      ...currentUser.user_profile,
      addl_field_flag: true
    }
  }

  return mutateAsync(users.editProfileMutation(updatedUser))
}

const mapStateToProps = createStructuredSelector({
  courses:         coursesSelector,
  currentUser:     currentUserSelector,
  courseIsLoading: pathOr(true, ["queries", coursesQueryKey, "isPending"]),
  courseStatus:    pathOr(true, ["queries", coursesQueryKey, "status"]),
  countries:       queries.users.countriesSelector
})

const mapPropsToConfig = props => [
  coursesQuery(props.courseId),
  users.currentUserQuery()
]

const mapDispatchToProps = {
  createEnrollment,
  addToCart,
  deactivateEnrollment,
  updateAddlFields,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(CourseProductDetailEnroll)
