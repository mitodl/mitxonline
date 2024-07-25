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
import { getFlexiblePriceForProduct, formatLocalePrice } from "../lib/util"
import { EnrollmentFlaggedCourseRun } from "../flow/courseTypes"
import {
  coursesSelector,
  coursesQuery,
  coursesQueryKey
} from "../lib/queries/courseRuns"

import { formatPrettyDate, emptyOrNil } from "../lib/util"
import moment from "moment-timezone"
import {
  getFirstRelevantRun,
  isRunArchived,
} from "../lib/courseApi"
import { getCookie } from "../lib/api"
import users, { currentUserSelector } from "../lib/queries/users"
import {
  enrollmentMutation,
  deactivateEnrollmentMutation
} from "../lib/queries/enrollment"
import AddlProfileFieldsForm from "./forms/AddlProfileFieldsForm"
import CourseInfoBox from "./CourseInfoBox"

import type { User } from "../flow/authTypes"
import type { Product } from "../flow/cartTypes"

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
  deactivateEnrollment: (runId: number) => Promise<any>,
  updateAddlFields: (currentUser: User) => Promise<any>,
  forceRequest: () => any
}
type ProductDetailState = {
  upgradeEnrollmentDialogVisibility: boolean,
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

  redirectToCourseHomepage(url: string, ev: any) {
    /*
    If we've got addl_field_flag, then display the extra info modal. Otherwise,
    send the learner directly to the page.
    */

    const { currentUser, updateAddlFields } = this.props

    if (currentUser.user_profile && currentUser.user_profile.addl_field_flag) {
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

  renderRunSelectorButtons() {
    const { courses } = this.props
    const courseRuns = courses && courses[0] ? courses[0].courseruns : null
    const enrollableCourseRuns = courseRuns ?
      courseRuns.filter(
        (run: EnrollmentFlaggedCourseRun) => run.is_enrollable
      ) :
      []
    return (
      <>
        {courseRuns && courseRuns.length > 1 ? (
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
    const csrfToken = getCookie("csrftoken")

    return (
      <form action="/enrollments/" method="post">
        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
        <input type="hidden" name="run" value={run ? run.id : ""} />
        <button
          type="submit"
          className="btn enroll-now enroll-now-free"
          disabled={!run || !run.is_enrollable}
        >
          <strong>Enroll for Free</strong> without a certificate
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

  renderUpgradeEnrollmentDialog(firstRelevantRun: EnrollmentFlaggedCourseRun) {
    const { courses } = this.props
    const courseRuns = courses && courses[0] ? courses[0].courseruns : null
    const course = courses && courses[0] ? courses[0] : null
    let run = this.getCurrentCourseRun()
    const hasMultipleEnrollableRuns = courseRuns && courseRuns.length > 1
    if (!run && !hasMultipleEnrollableRuns) {
      run = firstRelevantRun
    }
    const needFinancialAssistanceLink =
      run &&
      course &&
      course.page &&
      course.page.financial_assistance_form_url &&
      !run.approved_flexible_price_exists ? (
          <p className="financial-assistance-link">
            <a
              href={
                course && course.page && course.page.financial_assistance_form_url
              }
            >
            Need financial assistance?
            </a>
          </p>
        ) : null
    const { upgradeEnrollmentDialogVisibility } = this.state
    const product = run && run.products ? run.products[0] : null
    const canUpgrade = !!(run && run.is_upgradable && product)
    const upgradableCourseRuns = courseRuns ?
      courseRuns.filter(
        (run: EnrollmentFlaggedCourseRun) => run.is_upgradable
      ) :
      []

    return upgradableCourseRuns.length > 0 || hasMultipleEnrollableRuns ? (
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
          {hasMultipleEnrollableRuns ? (
            <div className="row date-selector-button-bar">
              <div className="col-12">
                <div>{this.renderRunSelectorButtons()}</div>
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
                    Certificate track:{" "}
                    <strong id="certificate-price-info">
                      {product &&
                        run.is_upgradable &&
                        formatLocalePrice(getFlexiblePriceForProduct(product))}
                    </strong>
                    <>
                      <br />
                      {canUpgrade ? (
                        <span className="text-danger">
                          Payment date:{" "}
                          {formatPrettyDate(moment(run.upgrade_deadline))}
                        </span>
                      ) : (
                        <strong id="certificate-price-info">
                          not available
                        </strong>
                      )}
                    </>
                  </p>
                </div>
                <div className="col-md-6 col-sm-12 pr-0 enroll-and-pay">
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
                      className="btn btn-upgrade"
                      disabled={!canUpgrade}
                    >
                      <strong>Enroll and Pay</strong>
                      <br />
                      <span>for the certificate track</span>
                    </button>
                  </form>
                </div>
              </div>
            </>
          ) : null}
          <div className="row upgrade-options-row">
            <div>{needFinancialAssistanceLink}</div>
            <div>{this.getEnrollmentForm(run)}</div>
          </div>
        </ModalBody>
      </Modal>
    ) : null
  }

  renderAddlProfileFieldsModal() {
    const { currentUser } = this.props
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
                To help us with our education research missions, please tell us
                more about yourself.
              </p>
            </div>
          </div>

          <AddlProfileFieldsForm
            onSubmit={this.saveProfile.bind(this)}
            onCancel={() => this.toggleAddlProfileFieldsModal()}
            user={currentUser}
            requireTypeFields={true}
          ></AddlProfileFieldsForm>
        </ModalBody>
      </Modal>
    )
  }

  renderEnrollLoginButton(run: EnrollmentFlaggedCourseRun) {
    return (
      <h2>
        <a
          href={`${routes.login}?next=${encodeURIComponent(
            window.location.pathname
          )}`}
          className="btn btn-primary btn-enrollment-button btn-lg  btn-gradient-red-to-blue highlight"
        >
          {isRunArchived(run) ? "Access Course Materials" : "Enroll Now"}
        </a>
      </h2>
    )
  }

  renderAccessCourseButton() {
    return (
      <h2>
        <button
          onClick={() =>
            (window.location = `${routes.login}?next=${encodeURIComponent(
              window.location.pathname
            )}`)
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
    product: Product | null
  ) {
    const { courses } = this.props
    const courseRuns = courses && courses[0] ? courses[0].courseruns : null
    const csrfToken = getCookie("csrftoken")
    return run ? (
      <h2>
        {(product && run.is_upgradable) ||
        (courseRuns && courseRuns.length > 1) ? (
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
                {isRunArchived(run) ? "Access Course Materials" : "Enroll Now"}
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
    if (courses) {
      const courseRuns = courses[0] ? courses[0].courseruns : null
      if (courseRuns) {
        run = getFirstRelevantRun(courses[0], courseRuns)

        if (run) {
          product = run && run.products ? run.products[0] : null
          this.updateDate(run)
        }
      }
    }

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
                  this.renderEnrollNowButton(run, product) :
                  this.renderEnrollLoginButton(run) :
                this.renderAccessCourseButton()}

              {run && currentUser ? this.renderAddlProfileFieldsModal() : null}
              {run ? this.renderUpgradeEnrollmentDialog(run) : null}
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
  courseStatus:    pathOr(true, ["queries", coursesQueryKey, "status"])
})

const mapPropsToConfig = props => [
  coursesQuery(props.courseId),
  users.currentUserQuery()
]

const mapDispatchToProps = {
  createEnrollment,
  deactivateEnrollment,
  updateAddlFields
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(CourseProductDetailEnroll)
