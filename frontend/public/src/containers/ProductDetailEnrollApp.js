// @flow
import React, { Fragment } from "react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest, mutateAsync } from "redux-query"
import { Modal, ModalBody, ModalHeader } from "reactstrap"

import Loader from "../components/Loader"
import { routes } from "../lib/urls"
import { getFlexiblePriceForProduct, formatLocalePrice } from "../lib/util"
import { EnrollmentFlaggedCourseRun } from "../flow/courseTypes"
import {
  courseRunsSelector,
  courseRunsQuery,
  courseRunsQueryKey
} from "../lib/queries/courseRuns"

import { formatPrettyDate, emptyOrNil } from "../lib/util"
import moment from "moment-timezone"
import {
  isFinancialAssistanceAvailable,
  isWithinEnrollmentPeriod
} from "../lib/courseApi"
import { getCookie } from "../lib/api"
import type { User } from "../flow/authTypes"
import users, { currentUserSelector } from "../lib/queries/users"
import { enrollmentMutation } from "../lib/queries/enrollment"
import { checkFeatureFlag } from "../lib/util"
import AddlProfileFieldsForm from "../components/forms/AddlProfileFieldsForm"

type Props = {
  courseId: string,
  isLoading: ?boolean,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  status: ?number,
  upgradeEnrollmentDialogVisibility: boolean,
  addProductToBasket: (user: number, productId: number) => Promise<any>,
  currentUser: User,
  createEnrollment: (runId: number) => Promise<any>,
  updateAddlFields: (currentUser: User) => Promise<any>
}
type ProductDetailState = {
  upgradeEnrollmentDialogVisibility: boolean,
  showAddlProfileFieldsModal: boolean,
  currentCourseRun: ?EnrollmentFlaggedCourseRun,
  destinationUrl: string
}

export class ProductDetailEnrollApp extends React.Component<
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

    if (
      !checkFeatureFlag("enable_addl_profile_fields") ||
      (currentUser.user_profile && currentUser.user_profile.addl_field_flag)
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
    const { createEnrollment, courseRuns } = this.props
    const run =
      !this.getCurrentCourseRun() && courseRuns
        ? courseRuns[0]
        : this.getCurrentCourseRun()

    if (!upgradeEnrollmentDialogVisibility) {
      console.log(`creating enrollment for ${run.id}`)
      createEnrollment(run)
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

  getCurrentCourseRun = (): EnrollmentFlaggedCourseRun => {
    return this.state.currentCourseRun
  }

  renderUpgradeEnrollmentDialog() {
    const { courseRuns } = this.props
    const run =
      !this.getCurrentCourseRun() && courseRuns
        ? courseRuns[0]
        : this.getCurrentCourseRun()
    const needFinancialAssistanceLink =
      isFinancialAssistanceAvailable(run) &&
      !run.approved_flexible_price_exists ? (
          <p className="text-center financial-assistance-link">
            <a href={run.page.financial_assistance_form_url}>
            Need financial assistance?
            </a>
          </p>
        ) : null
    const { upgradeEnrollmentDialogVisibility } = this.state
    const product = run.products ? run.products[0] : null

    return product ? (
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
            <div className="text-right align-self-end">
              {formatLocalePrice(getFlexiblePriceForProduct(product))}
            </div>
          </div>
          <div className="row">
            <div className="col-12">
              <p>
                Thank you for choosing an MITx online course. By paying for this
                course, you're joining the most engaged and motivated learners
                on your path to a certificate from MITx.
              </p>

              <p>
                Your certificate is signed by MIT faculty and demonstrates that
                you have gained the knowledge and skills taught in this course.
                Showcase your certificate on your resume and social channels to
                advance your career, earn a promotion, or enhance your college
                applications.
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
          <div className="cancel-link">{this.getEnrollmentForm()}</div>
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
    ) : null
  }

  getEnrollmentForm() {
    return (
      <form>
        <button type="submit" className="btn enroll-now enroll-now-free">
          No thanks, I'll take the free version without a certificate
        </button>
      </form>
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

  render() {
    const { courseRuns, isLoading, currentUser } = this.props
    const csrfToken = getCookie("csrftoken")
    let run =
      !this.getCurrentCourseRun() && courseRuns
        ? courseRuns[0]
        : this.getCurrentCourseRun() && courseRuns
          ? courseRuns[0].page && this.getCurrentCourseRun().page
            ? courseRuns[0].page.page_url ===
            this.getCurrentCourseRun().page.page_url
              ? this.getCurrentCourseRun()
              : courseRuns[0]
            : courseRuns[0]
          : null
    if (run) this.updateDate(run)
    let product = run && run.products ? run.products[0] : null
    if (courseRuns) {
      const thisScope = this
      courseRuns.map(courseRun => {
        // $FlowFixMe
        document.addEventListener("click", function(e) {
          if (e.target && e.target.id === courseRun.courseware_id) {
            thisScope.setCurrentCourseRun(courseRun)
            run = thisScope.getCurrentCourseRun()
            product = run && run.products ? run.products[0] : null
            // $FlowFixMe
            thisScope.updateDate(run)
          }
        })
      })
    }

    const startDate =
      run && !emptyOrNil(run.start_date)
        ? moment(new Date(run.start_date))
        : null
    const disableEnrolledBtn = moment().isBefore(startDate) ? "disabled" : ""
    const waitingForCourseToBeginMessage = moment().isBefore(startDate) ? (
      <p style={{ fontSize: "16px" }}>
        Enrolled and waiting for the course to begin.
      </p>
    ) : null

    return (
      // $FlowFixMe: isLoading null or undefined
      <Loader isLoading={isLoading}>
        {run && run.is_enrolled ? (
          <Fragment>
            {run.courseware_url ? (
              <a
                href={run.courseware_url}
                onClick={ev =>
                  this.redirectToCourseHomepage(run.courseware_url, ev)
                }
                className={`btn btn-primary btn-gradient-red highlight outline ${disableEnrolledBtn}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                Enrolled &#10003;
              </a>
            ) : (
              <div
                className={`btn btn-primary btn-gradient-red highlight outline ${disableEnrolledBtn}`}
              >
                Enrolled &#10003;
              </div>
            )}
            {waitingForCourseToBeginMessage}
          </Fragment>
        ) : (
          <Fragment>
            {run &&
            isWithinEnrollmentPeriod(run) &&
            currentUser &&
            !currentUser.id ? (
                <a
                  href={routes.login}
                  className="btn btn-primary btn-gradient-red highlight"
                >
                Enroll now
                </a>
              ) : run && isWithinEnrollmentPeriod(run) ? (
                product && run.is_upgradable ? (
                  <button
                    className="btn btn-primary btn-gradient-red highlight enroll-now"
                    onClick={() => this.toggleUpgradeDialogVisibility()}
                  >
                  Enroll now
                  </button>
                ) : (
                  <Fragment>
                    <form action="/enrollments/" method="post">
                      <input
                        type="hidden"
                        name="csrfmiddlewaretoken"
                        value={csrfToken}
                      />
                      <input type="hidden" name="run" value={run ? run.id : ""} />
                      <button
                        type="submit"
                        className="btn btn-primary btn-gradient-red highlight enroll-now"
                      >
                      Enroll now
                      </button>
                    </form>
                  </Fragment>
                )
              ) : null}
            {run ? this.renderUpgradeEnrollmentDialog() : null}
          </Fragment>
        )}
        {currentUser ? this.renderAddlProfileFieldsModal() : null}
      </Loader>
    )
  }
}

const createEnrollment = (run: EnrollmentFlaggedCourseRun) =>
  mutateAsync(enrollmentMutation(run.id))

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
  courseRuns:  courseRunsSelector,
  currentUser: currentUserSelector,
  isLoading:   pathOr(true, ["queries", courseRunsQueryKey, "isPending"]),
  status:      pathOr(null, ["queries", courseRunsQueryKey, "status"])
})

const mapPropsToConfig = props => [
  courseRunsQuery(props.courseId),
  users.currentUserQuery()
]

const mapDispatchToProps = {
  createEnrollment,
  updateAddlFields
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(ProductDetailEnrollApp)
