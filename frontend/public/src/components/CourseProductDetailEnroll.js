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
import { EnrollmentFlaggedCourseRun, RunEnrollment } from "../flow/courseTypes"
import {
  courseRunsSelector,
  courseRunsQuery,
  courseRunsQueryKey,
  coursesSelector,
  coursesQuery,
  coursesQueryKey
} from "../lib/queries/courseRuns"
import {
  enrollmentsQuery,
  enrollmentsQueryKey,
  enrollmentsSelector
} from "../lib/queries/enrollment"

import { formatPrettyDate, emptyOrNil } from "../lib/util"
import moment from "moment-timezone"
import {
  getFirstRelevantRun,
  isFinancialAssistanceAvailable,
  isWithinEnrollmentPeriod
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
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  courses: ?Array<any>,
  enrollments: ?Array<RunEnrollment>,
  status: ?number,
  courseIsLoading: ?boolean,
  courseStatus: ?number,
  enrollmentsIsLoading: ?boolean,
  enrollmentsStatus: ?number,
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

  resolveFirstEnrollableRun() {
    const { courseRuns } = this.props

    const enrollableRun =
      courseRuns &&
      courseRuns
        .sort(
          (a: EnrollmentFlaggedCourseRun, b: EnrollmentFlaggedCourseRun) => {
            if (moment(a.start_date).isBefore(moment(b.start_date))) {
              return -1
            } else if (moment(a.start_date).isAfter(moment(b.start_date))) {
              return 1
            } else {
              return 0
            }
          }
        )
        .find((run: EnrollmentFlaggedCourseRun) => {
          return (
            (run.enrollment_start === null ||
              moment(run.enrollment_start).isBefore(moment.now())) &&
            (run.enrollment_end === null ||
              moment(run.enrollment_end).isAfter(moment.now()))
          )
        })

    return enrollableRun || (courseRuns && courseRuns[0])
  }

  resolveCurrentRun() {
    const { courseRuns } = this.props

    return !this.getCurrentCourseRun() && courseRuns
      ? this.resolveFirstEnrollableRun()
      : this.getCurrentCourseRun()
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

  async checkForExistingEnrollment(run: EnrollmentFlaggedCourseRun) {
    // Find an existing enrollment - the default should be the audit enrollment
    // already have, so you can just upgrade in place. If you don't, you get the
    // current run (which should be the first available one).
    // This was changed to also make sure the run you're enrolled in is upgradeable.
    const { enrollments } = this.props

    if (enrollments) {
      const firstAuditEnrollment = enrollments.find(
        (enrollment: RunEnrollment) =>
          enrollment.run.course.id === run.course.id &&
          enrollment.enrollment_mode === "audit" &&
          enrollment.run.enrollment_end !== null &&
          enrollment.run.enrollment_end > moment.now() &&
          (enrollment.run.upgrade_deadline === null ||
            enrollment.run.upgrade_deadline > moment.now())
      )

      if (firstAuditEnrollment) {
        this.setCurrentCourseRun(firstAuditEnrollment.run)
        return
      }
    }

    this.setCurrentCourseRun(run)
  }

  toggleUpgradeDialogVisibility = () => {
    const { upgradeEnrollmentDialogVisibility } = this.state
    const run = this.resolveCurrentRun()

    if (!upgradeEnrollmentDialogVisibility) {
      this.checkForExistingEnrollment(run)
    } else {
      window.location = "/dashboard/"
    }

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
    const { courseRuns } = this.props

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

  getFirstUnenrolledCourseRun = (): EnrollmentFlaggedCourseRun => {
    const { courseRuns } = this.props

    return courseRuns
      ? courseRuns.find(
        (run: EnrollmentFlaggedCourseRun) =>
          run.is_enrolled === false &&
            moment(run.enrollment_start) <= moment.now()
      ) || courseRuns[0]
      : null
  }

  cancelEnrollment() {
    const { upgradeEnrollmentDialogVisibility } = this.state

    this.setState({
      upgradeEnrollmentDialogVisibility: !upgradeEnrollmentDialogVisibility
    })
  }

  renderRunSelectorButtons(run: EnrollmentFlaggedCourseRun) {
    const { courseRuns } = this.props

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
          {courseRuns &&
            courseRuns.map((elem: EnrollmentFlaggedCourseRun) => (
              <option
                selected={run.id === elem.id}
                value={elem.id}
                key={`courserun-selection-${elem.id}`}
              >
                {formatPrettyDate(moment(new Date(elem.start_date)))} -{" "}
                {formatPrettyDate(moment(new Date(elem.end_date)))}{" "}
                {elem.is_upgradable ? "(can upgrade)" : ""}
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
        <button type="submit" className="btn enroll-now enroll-now-free">
          <strong>Enroll for Free</strong> without a certificate
        </button>
      </form>
    )
  }

  updateDate(run: EnrollmentFlaggedCourseRun) {
    // for original design - not used in course infobox design
    let date = emptyOrNil(run.start_date)
      ? undefined
      : moment(new Date(run.start_date))
    date = date ? date.utc() : date
    const dateElem = document.getElementById("start_date")
    if (dateElem) {
      dateElem.innerHTML = `<strong>${formatPrettyDate(date)}</strong>`
    }
  }

  renderUpgradeEnrollmentDialog() {
    const { courseRuns, courses } = this.props
    const run = this.resolveCurrentRun()
    const course =
      courses &&
      courses.find(
        (elem: any) => run && run.course && elem.id === run.course.id
      )
    const needFinancialAssistanceLink =
      run &&
      isFinancialAssistanceAvailable(run) &&
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
    const upgradableCourseRuns = courseRuns
      ? courseRuns.filter(
        (run: EnrollmentFlaggedCourseRun) => run.is_upgradable
      )
      : []

    return run ? (
      <Modal
        id={`upgrade-enrollment-dialog`}
        className="upgrade-enrollment-modal"
        isOpen={upgradeEnrollmentDialogVisibility}
        toggle={() => this.cancelEnrollment()}
        centered
      >
        <ModalHeader toggle={() => this.cancelEnrollment()}>
          {run.title}
        </ModalHeader>
        <ModalBody>
          {courseRuns.length > 1 ? (
            <div className="row date-selector-button-bar">
              <div className="col-12">
                <div>{this.renderRunSelectorButtons(run)}</div>
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
                <div className="col-md-6 col-sm-12 certificate-pricing d-flex align-items-center">
                  <div className="certificate-pricing-logo">
                    <img src="/static/images/certificates/certificate-logo.svg" />
                  </div>
                  <p>
                    Certificate track:{" "}
                    <strong id="certificate-price-info">
                      {product &&
                        formatLocalePrice(getFlexiblePriceForProduct(product))}
                    </strong>
                    <>
                      <br />
                      {product && run.upgrade_deadline ? (
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
                      value={product && product.id}
                    />
                    <button
                      type="submit"
                      className="btn btn-upgrade"
                      disabled={!product}
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

  renderEnrollLoginButton() {
    const { currentUser } = this.props
    return !currentUser || !currentUser.id ? (
      <h2>
        <a
          href={`${routes.login}?next=${encodeURIComponent(
            window.location.pathname
          )}`}
          className="btn btn-primary btn-enrollment-button btn-lg btn-gradient-red highlight"
        >
          Enroll now
        </a>
      </h2>
    ) : null
  }

  renderEnrollNowButton(
    run: EnrollmentFlaggedCourseRun,
    product: Product | null
  ) {
    const { currentUser } = this.props
    const csrfToken = getCookie("csrftoken")
    return currentUser &&
      currentUser.id &&
      run &&
      isWithinEnrollmentPeriod(run) ? (
        <h2>
          <button
            id="upgradeEnrollBtn"
            className="btn btn-primary btn-enrollment-button btn-lg btn-gradient-red highlight enroll-now"
            onClick={() => this.toggleUpgradeDialogVisibility()}
          >
          Enroll now
          </button>
        </h2>
      ) : null
  }

  render() {
    const {
      courseRuns,
      isLoading,
      courses,
      courseIsLoading,
      currentUser,
      enrollments,
      enrollmentsIsLoading
    } = this.props
    let run,
      product = null

    if (courses && courseRuns) {
      run = getFirstRelevantRun(courses[0], courseRuns)

      if (run) {
        product = run && run.products ? run.products[0] : null
        this.updateDate(run)
      }
    }

    return run ? (
      <>
        {
          // $FlowFixMe: isLoading null or undefined
          <Loader key="product_detail_enroll_loader" isLoading={isLoading}>
            <>
              {this.renderEnrollLoginButton()}
              {this.renderEnrollNowButton(run, product)}

              {currentUser ? this.renderAddlProfileFieldsModal() : null}
              {run ? this.renderUpgradeEnrollmentDialog() : null}
            </>
          </Loader>
        }
        <>
          {
            // $FlowFixMe: isLoading null or undefined
            <Loader
              key="course_info_loader"
              isLoading={courseIsLoading || enrollmentsIsLoading}
            >
              <CourseInfoBox
                courses={courses}
                courseRuns={courseRuns}
                currentUser={currentUser}
                toggleUpgradeDialogVisibility={
                  this.toggleUpgradeDialogVisibility
                }
                setCurrentCourseRun={this.setCurrentCourseRun}
                enrollments={enrollments}
              ></CourseInfoBox>
            </Loader>
          }
        </>
      </>
    ) : null
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
  courseRuns:           courseRunsSelector,
  courses:              coursesSelector,
  currentUser:          currentUserSelector,
  enrollments:          enrollmentsSelector,
  isLoading:            pathOr(true, ["queries", courseRunsQueryKey, "isPending"]),
  courseIsLoading:      pathOr(true, ["queries", coursesQueryKey, "isPending"]),
  enrollmentsIsLoading: pathOr(true, [
    "queries",
    enrollmentsQueryKey,
    "isPending"
  ]),
  status:            pathOr(null, ["queries", courseRunsQueryKey, "status"]),
  courseStatus:      pathOr(true, ["queries", coursesQueryKey, "status"]),
  enrollmentsStatus: pathOr(true, ["queries", enrollmentsQueryKey, "status"])
})

const mapPropsToConfig = props => [
  courseRunsQuery(props.courseId),
  coursesQuery(props.courseId),
  enrollmentsQuery(),
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
