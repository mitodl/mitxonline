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
import { EnrollmentFlaggedCourseRun } from "../flow/courseTypes"
import {
  courseRunsSelector,
  courseRunsQuery,
  courseRunsQueryKey
} from "../lib/queries/courseRuns"

import { isWithinEnrollmentPeriod } from "../lib/courseApi"

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
  upgradeEnrollmentDialogVisibility: boolean
}

export class ProductDetailEnrollApp extends React.Component<
  Props,
  ProductDetailState
> {
  state = {
    upgradeEnrollmentDialogVisibility: false
  }

  toggleUpgradeDialogVisibility = () => {
    const { upgradeEnrollmentDialogVisibility } = this.state
    this.setState({
      upgradeEnrollmentDialogVisibility: !upgradeEnrollmentDialogVisibility
    })
  }

  renderUpgradeEnrollmentDialog(run: EnrollmentFlaggedCourseRun) {
    const { courseRuns } = this.props
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
          <div className="row modal-subheader">
            <div className="col-10">Take a course and get a certificate</div>
            <div className="col-2">${product.price}</div>
          </div>
          <div className="row">
            <div className="col-4">
              <div className="upgrade-icon" />
            </div>
            <div className="col-8">
              <p>
                Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do
                eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut
                enim ad minim veniam, quis nostrud exercitation ullamco laboris
                nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor
                in reprehenderit in voluptate velit esse cillum dolore eu fugiat
                nulla pariatur. Excepteur sint occaecat cupidatat non proident,
                sunt in culpa qui officia deserunt mollit anim id est laborum.
              </p>

              <form action="/cart/add/" method="get">
                <input type="hidden" name="product_id" value={product.id} />
                <button
                  type="submit"
                  className="btn btn-primary btn-gradient-red"
                >
                  Continue
                </button>
              </form>
            </div>
          </div>
          <div className="cancel-link">{this.getEnrollmentForm()}</div>
        </ModalBody>
      </Modal>
    ) : null
  }
  getEnrollmentForm() {
    const csrfToken = getCookie("csrftoken")
    const { courseRuns } = this.props
    const run = courseRuns ? courseRuns[0] : null
    return (
      <form action="/enrollments/" method="post">
        <input type="hidden" name="csrfmiddlewaretoken" value={csrfToken} />
        <input type="hidden" name="run" value={run ? run.id : ""} />
        <button type="submit" className="btn enroll-now enroll-now-free">
          No thanks, I'll take the free version
        </button>
      </form>
    )
  }

  render() {
    const { courseRuns, isLoading, status } = this.props
    const csrfToken = getCookie("csrftoken")
    const run = courseRuns ? courseRuns[0] : null

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
              SETTINGS.features.upgrade_dialog ? (
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
              ? this.renderUpgradeEnrollmentDialog(run)
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
