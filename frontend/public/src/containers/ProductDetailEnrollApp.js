// @flow
/* global SETTINGS:false */
import React, { Fragment } from "react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest } from "redux-query"
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

import {isFinancialAssistanceAvailable, isWithinEnrollmentPeriod} from "../lib/courseApi"
import { formatPrettyDate, parseDateString } from "../lib/util"
import { getCookie } from "../lib/api"
import type { User } from "../flow/authTypes"
import users, { currentUserSelector } from "../lib/queries/users"

type Props = {
  courseId: string,
  isLoading: ?boolean,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  status: ?number,
  upgradeEnrollmentDialogVisibility: boolean,
  addProductToBasket: (user: number, productId: number) => Promise<any>,
  currentUser: User
}
type ProductDetailState = {
  upgradeEnrollmentDialogVisibility: boolean,
  currentCourseRun:                  ?EnrollmentFlaggedCourseRun
}

export class ProductDetailEnrollApp extends React.Component<
  Props,
  ProductDetailState
> {
  state = {
    upgradeEnrollmentDialogVisibility: false,
    currentCourseRun:                  null,
  }

  toggleUpgradeDialogVisibility = () => {
    const { upgradeEnrollmentDialogVisibility } = this.state
    this.setState({
      upgradeEnrollmentDialogVisibility: !upgradeEnrollmentDialogVisibility
    })
  }

  setCurrentCourseRun = (courseRun: EnrollmentFlaggedCourseRun) => {
    sessionStorage.setItem('currentCourseRun', JSON.stringify(courseRun))
    this.setState({
      currentCourseRun: courseRun
    })
  }

  getCurrentCourseRun = (): EnrollmentFlaggedCourseRun => {
    const sessionCourseRun = JSON.parse(sessionStorage.getItem('currentCourseRun'))
    return sessionCourseRun ? sessionCourseRun : this.state.currentCourseRun
  }

  renderUpgradeEnrollmentDialog() {
    const { courseRuns } = this.props
    const run = !this.getCurrentCourseRun() && courseRuns ? courseRuns[0] : this.getCurrentCourseRun()
    const needFinancialAssistanceLink = isFinancialAssistanceAvailable(run) ?
      (
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
            <div className="text-right align-self-end">{formatLocalePrice(getFlexiblePriceForProduct(product))}</div>
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
          <div className="cancel-link">{this.getEnrollmentForm(run)}</div>
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
  getEnrollmentForm(run: EnrollmentFlaggedCourseRun) {
    const csrfToken = getCookie("csrftoken")
    return (
      <form action="/enrollments/" method="post">
        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
        <input type="hidden" name="run" value={run ? run.id : ""} />
        <button type="submit" className="btn enroll-now enroll-now-free">
          No thanks, I'll take the free version without a certificate
        </button>
      </form>
    )
  }

  updateDate(run) {
    const date = parseDateString(new Date(run.start_date)).utc()
    document.getElementById('start_date').innerHTML = `<strong>${formatPrettyDate(date)}</strong>`
  }

  render() {
    const { courseRuns, isLoading, status } = this.props
    const csrfToken = getCookie("csrftoken")
    let run = !this.getCurrentCourseRun() && courseRuns ? (
      courseRuns[0]
    ) : (
      this.getCurrentCourseRun() && courseRuns ? (
        courseRuns[0].page.page_url === this.getCurrentCourseRun().page.page_url ? (
          this.getCurrentCourseRun()
        ) : (
          courseRuns[0]
        )
      ) : (
        null
      )
    )
    if (run) this.updateDate(run)
    let product = run && run.products ? run.products[0] : null
    if (courseRuns) {
      const thisScope = this
      courseRuns.map(courseRun => {
        // $FlowFixMe
        document.addEventListener('click', function(e) {
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

    return (
      // $FlowFixMe: isLoading null or undefined
      <Loader isLoading={isLoading}>
        {run && run.is_enrolled ? (
          <Fragment>
            {run.courseware_url ? (
              <a
                href={run.courseware_url}
                className="btn btn-primary btn-gradient-red highlight outline"
                target="_blank"
                rel="noopener noreferrer"
              >
                Enrolled &#10003;
              </a>
            ) : (
              <div className="btn btn-primary btn-gradient-red highlight outline">
                Enrolled &#10003;
              </div>
            )}
          </Fragment>
        ) : (
          <Fragment>
            {status === 403 ? (
              <a
                href={routes.login}
                className="btn btn-primary btn-gradient-red highlight"
              >
                Enroll now
              </a>
            ) : run && isWithinEnrollmentPeriod(run) ? (
              SETTINGS.features.upgrade_dialog && product ? (
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
            {SETTINGS.features.upgrade_dialog && run
              ? this.renderUpgradeEnrollmentDialog()
              : null}
          </Fragment>
        )}
      </Loader>
    )
  }
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

export default compose(
  connect(mapStateToProps),
  connectRequest(mapPropsToConfig)
)(ProductDetailEnrollApp)
