// @flow
import React, { Fragment } from "react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest, mutateAsync } from "redux-query"
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
  isFinancialAssistanceAvailable,
  isWithinEnrollmentPeriod
} from "../lib/courseApi"
import { getCookie } from "../lib/api"
import users, { currentUserSelector } from "../lib/queries/users"
import {
  enrollmentMutation,
  deactivateEnrollmentMutation
} from "../lib/queries/enrollment"
import { checkFeatureFlag } from "../lib/util"
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

  resolveCurrentRun() {
    const { courseRuns } = this.props

    return !this.getCurrentCourseRun() && courseRuns
      ? courseRuns[0]
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
    const { enrollments } = this.props

    if (enrollments) {
      const firstAuditEnrollment = enrollments.find(
        (elem: RunEnrollment) =>
          elem.run.course.id === run.course.id &&
          elem.enrollment_mode === "audit"
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

  getFirstUnexpiredRun = () => {
    const { courses, courseRuns } = this.props
    return courseRuns
      ? courses && courses[0].next_run_id
        ? courseRuns.find(elem => elem.id === courses[0].next_run_id)
        : courseRuns[0]
      : null
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
        <label htmlFor="choose-courserun">Choose a date:</label>
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
                {formatPrettyDate(moment(new Date(elem.end_date)))}
              </option>
            ))}
        </select>
      </>
    )
  }

  getEnrollmentForm(run: EnrollmentFlaggedCourseRun, showNewDesign: boolean) {
    const csrfToken = getCookie("csrftoken")

    return showNewDesign ? (
      <form action="/enrollments/" method="post">
        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
        <input type="hidden" name="run" value={run ? run.id : ""} />
        <button type="submit" className="btn enroll-now enroll-now-free">
          Or, Enroll for Free without a certificate
        </button>
      </form>
    ) : (
      <div className="d-flex">
        <div className="flex-grow-1 w-auto">
          <form action="/enrollments/" method="post">
            <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
            <input type="hidden" name="run" value={run ? run.id : ""} />
            <button type="submit" className="btn enroll-now enroll-now-free">
              No thanks, I'll take the course for free without a certificate
            </button>
          </form>
        </div>
        <div className="ml-auto">
          <button
            onClick={this.cancelEnrollment.bind(this)}
            className="btn enroll-now enroll-now-free cancel-enrollment-button"
          >
            Cancel Enrollment
          </button>
        </div>
      </div>
    )
  }

  updateDate(run: EnrollmentFlaggedCourseRun) {
    let date = emptyOrNil(run.start_date)
      ? undefined
      : moment(new Date(run.start_date))
    date = date ? date.utc() : date
    const dateElem = document.getElementById("start_date")
    if (dateElem) {
      dateElem.innerHTML = `<strong>${formatPrettyDate(date)}</strong>`
    }
  }

  renderUpgradeEnrollmentDialog(showNewDesign: boolean) {
    const { courseRuns, courses } = this.props
    const run = this.resolveCurrentRun()

    const course =
      courses && courses.find((elem: any) => elem.id === run.course.id)
    const needFinancialAssistanceLink =
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
    const product = run.products ? run.products[0] : null

    return product ? (
      showNewDesign ? (
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
            {courseRuns && courseRuns.length > 1 ? (
              <div className="row date-selector-button-bar">
                <div className="col-12">
                  <div>{this.renderRunSelectorButtons(run)}</div>
                </div>
              </div>
            ) : null}

            <div className="row upsell-messaging-header">
              <div className="col-12 p-0 font-weight-bold">
                Acheiving a certificate has its advantages:
              </div>
            </div>

            <div className="row">
              <div className="col-6">
                <ul>
                  <li> Certificate is signed by MIT faculty</li>
                  <li>
                    {" "}
                    Demonstrates knowledge and skills taught in this course
                  </li>
                  <li> Enhance your college &amp; earn a promotion</li>
                </ul>
              </div>
              <div className="col-6">
                <ul>
                  <li>Highlight on your resume/CV</li>
                  <li>Share on your social channels &amp; LinkedIn</li>
                  <li>
                    Enhance your college application with an earned certificate
                    from MIT
                  </li>
                </ul>
              </div>
            </div>

            <div className="row certificate-pricing-row">
              <div className="col-6 certificate-pricing d-flex align-items-center">
                <div className="certificate-pricing-logo">
                  <svg viewBox="0 0 40 44" xmlns="http://www.w3.org/2000/svg">
                    <path
                      fillRule="evenodd"
                      clipRule="evenodd"
                      d="M33.1301 23.314L39.8422 34.7838C40.1671 35.3396 39.9743 36.0504 39.4115 36.3713C39.2329 36.4731 39.0303 36.5269 38.8241 36.527L31.4033 36.6337L27.6205 42.9098C27.5701 42.9923 27.5099 43.0684 27.4413 43.1368C27.2159 43.3603 26.9102 43.4868 26.5909 43.4887C26.5404 43.4887 26.4921 43.484 26.4439 43.4796C26.0796 43.4373 25.756 43.23 25.5683 42.9189L20.0007 33.3956L14.4279 42.9189C14.2471 43.2273 13.9335 43.4372 13.5764 43.4887C13.5208 43.4957 13.4648 43.4996 13.4087 43.5C13.1067 43.4999 12.8165 43.3852 12.5974 43.18C12.5117 43.0995 12.4364 43.0087 12.3733 42.9098L8.59171 36.6337L1.17668 36.527C0.756404 36.5209 0.370025 36.2979 0.158594 35.9391C-0.0503957 35.5823 -0.052981 35.143 0.151699 34.7838L6.86076 23.3192C5.49809 21.0597 4.70092 18.429 4.70092 15.6081C4.70092 7.26415 11.5494 0.5 19.9975 0.5C28.4456 0.5 35.2941 7.26415 35.2941 15.6081C35.2908 18.4271 34.4926 21.0559 33.1301 23.314ZM10.2775 34.8859L13.388 40.0475L18.8818 30.6606C14.6737 30.3598 10.9406 28.3867 8.3615 25.4002L3.19336 34.2322L9.2835 34.3184C9.69214 34.3244 10.0683 34.5392 10.2775 34.8859ZM19.9972 28.392C15.4671 28.392 11.4865 26.0893 9.17387 22.6084C9.17309 22.6075 9.17243 22.6064 9.17182 22.6054C9.17134 22.6046 9.17088 22.6037 9.17043 22.6028C9.16945 22.601 9.16845 22.5991 9.16712 22.5974C7.83504 20.5879 7.05396 18.1895 7.05396 15.6082C7.05396 8.54801 12.8489 2.82445 19.9972 2.82445C27.1421 2.83282 32.932 8.55141 32.9405 15.6082C32.9405 18.1908 32.1588 20.5901 30.8256 22.6002L30.8253 22.6008C28.5135 26.0858 24.5306 28.392 19.9972 28.392ZM29.7162 34.8857C29.9258 34.5389 30.3024 34.3242 30.7113 34.3183L36.8015 34.232L31.6302 25.3931C29.1549 28.2601 25.6209 30.2062 21.6202 30.6274L21.3601 31.0721L26.6068 40.0474L29.7162 34.8857Z"
                      fill="#6F7175"
                    />
                  </svg>
                </div>
                <p>
                  Certitficate track:{" "}
                  <strong id="certificate-price-info">
                    {product &&
                      formatLocalePrice(getFlexiblePriceForProduct(product))}
                  </strong>
                  {run.upgrade_deadline ? (
                    <>
                      <br />
                      <span className="text-danger">
                        Payment date:{" "}
                        {formatPrettyDate(moment(run.upgrade_deadline))}
                      </span>
                    </>
                  ) : null}
                </p>
              </div>
              <div className="col-6 pr-0">
                <form action="/cart/add/" method="get" className="text-center">
                  <input type="hidden" name="product_id" value={product.id} />
                  <button type="submit" className="btn btn-upgrade">
                    <strong>Enroll and Pay</strong>
                    <br />
                    <span>for the certificate track</span>
                  </button>
                </form>
              </div>
            </div>

            <div className="row upgrade-options-row">
              <div>
                <p>{needFinancialAssistanceLink}</p>
              </div>
              <div>{this.getEnrollmentForm(run, showNewDesign)}</div>
            </div>
          </ModalBody>
        </Modal>
      ) : (
        <Modal
          id={`upgrade-enrollment-dialog`}
          className="upgrade-enrollment-modal"
          isOpen={upgradeEnrollmentDialogVisibility}
          toggle={() => this.toggleUpgradeDialogVisibility()}
        >
          <ModalHeader toggle={() => this.toggleUpgradeDialogVisibility()}>
            Enroll
          </ModalHeader>
          <ModalBody>
            <div className="row modal-subheader d-flex">
              <div className="flex-grow-1 align-self-end">
                Learn online and get a certificate
              </div>
              <div className="text-end align-self-end">
                {formatLocalePrice(getFlexiblePriceForProduct(product))}
              </div>
            </div>
            <div className="row">
              <div className="col-12">
                <p>
                  Thank you for choosing an MITx Online course. By paying for
                  this course, you're joining the most engaged and motivated
                  learners on your path to a certificate from MITx.
                </p>

                <p>
                  Your certificate is signed by MIT faculty and demonstrates
                  that you have gained the knowledge and skills taught in this
                  course. Showcase your certificate on your resume and social
                  channels to advance your career, earn a promotion, or enhance
                  your college applications.
                </p>

                <form action="/cart/add/" method="get" className="text-center">
                  <input type="hidden" name="product_id" value={product.id} />
                  <button
                    type="submit"
                    className="btn btn-primary btn-gradient-red"
                  >
                    Continue
                  </button>
                </form>
                {needFinancialAssistanceLink}
              </div>
            </div>
            <div className="cancel-link">
              {this.getEnrollmentForm(run, showNewDesign)}
            </div>
            <div className="faq-link">
              <a
                href="https://mitxonline.zendesk.com/hc/en-us"
                target="_blank"
                rel="noreferrer"
              >
                FAQs
              </a>
            </div>
          </ModalBody>
        </Modal>
      )
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

  renderEnrolledButton(run: EnrollmentFlaggedCourseRun) {
    const startDate =
      run && !emptyOrNil(run.start_date)
        ? moment(new Date(run.start_date))
        : null
    const waitingForCourseToBeginMessage = moment().isBefore(startDate) ? (
      <p style={{ fontSize: "16px" }}>
        Enrolled and waiting for the course to begin.
      </p>
    ) : null
    const disableEnrolledBtn = moment().isBefore(startDate) ? "disabled" : ""

    return run && run.is_enrolled ? (
      <>
        <Fragment>
          {run.courseware_url ? (
            <a
              href={run.courseware_url}
              onClick={ev =>
                run ? this.redirectToCourseHomepage(run.courseware_url, ev) : ev
              }
              className={`btn btn-primary btn-enrollment-button btn-gradient-red highlight outline ${disableEnrolledBtn}`}
              target="_blank"
              rel="noopener noreferrer"
            >
              Enrolled &#10003;
            </a>
          ) : (
            <div
              className={`btn btn-primary btn-enrollment-button btn-gradient-red highlight outline ${disableEnrolledBtn}`}
            >
              Enrolled &#10003;
            </div>
          )}
          {waitingForCourseToBeginMessage}
        </Fragment>
      </>
    ) : null
  }

  renderEnrollLoginButton() {
    const { currentUser } = this.props

    return !currentUser || !currentUser.id ? (
      <>
        <a
          href={routes.login}
          className="btn btn-primary btn-enrollment-button btn-lg btn-gradient-red highlight"
        >
          Enroll now
        </a>
      </>
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
      !run.is_enrolled &&
      isWithinEnrollmentPeriod(run) ? (
        <>
          {product && run.is_upgradable ? (
            <button
              id="upgradeEnrollBtn"
              className="btn btn-primary btn-enrollment-button btn-lg btn-gradient-red highlight enroll-now"
              onClick={() => this.toggleUpgradeDialogVisibility()}
            >
            Enroll now
            </button>
          ) : (
            <form action="/enrollments/" method="post">
              <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
              <input type="hidden" name="run" value={run ? run.id : ""} />
              <button
                type="submit"
                className="btn btn-primary btn-enrollment-button btn-gradient-red highlight enroll-now"
              >
              Enroll now
              </button>
            </form>
          )}
        </>
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
    const showNewDesign = checkFeatureFlag("mitxonline-new-product-page")

    let run,
      product = null

    if (courseRuns) {
      run = this.getFirstUnexpiredRun()

      if (run) {
        product = run && run.products ? run.products[0] : null
        this.updateDate(run)
      }
    }

    return (
      <>
        {
          // $FlowFixMe: isLoading null or undefined
          <Loader key="product_detail_enroll_loader" isLoading={isLoading}>
            <>
              {this.renderEnrolledButton(run)}
              {this.renderEnrollLoginButton()}
              {this.renderEnrollNowButton(run, product)}

              {currentUser ? this.renderAddlProfileFieldsModal() : null}
              {run ? this.renderUpgradeEnrollmentDialog(showNewDesign) : null}
            </>
          </Loader>
        }
        {showNewDesign ? (
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
        ) : null}
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
