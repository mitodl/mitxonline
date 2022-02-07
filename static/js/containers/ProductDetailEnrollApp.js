// @flow
/* global SETTINGS:false */
import React, { Fragment } from "react"
import { createStructuredSelector } from "reselect"
import { pathOr } from "ramda"
import { compose } from "redux"
import { connect } from "react-redux"
import { connectRequest, mutateAsync } from "redux-query"
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
import basket from "../lib/queries/basket"
import type { User } from "../flow/authTypes"
import users, { currentUserSelector } from "../lib/queries/users"
import { isSuccessResponse } from "../lib/util"
import { ALERT_TYPE_DANGER, ALERT_TYPE_SUCCESS } from "../constants"
import { addUserNotification } from "../actions"

type Props = {
  courseId: string,
  isLoading: ?boolean,
  courseRuns: ?Array<EnrollmentFlaggedCourseRun>,
  status: ?number,
  upgradeEnrollmentDialogVisibility: boolean,
  addProductToBasket: (user: number, productId: number) => Promise<any>,
  currentUser: User,
  addUserNotification: Function
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

  async addItemToBasket() {
    const {
      currentUser,
      courseRuns,
      addProductToBasket,
      addUserNotification
    } = this.props
    const run = courseRuns ? courseRuns[0] : null
    if (run === null) {
      return
    }
    const product = run.products ? run.products[0] : null
    if (product === null) {
      return
    }
    const resp = await addProductToBasket(currentUser.id, product.id)
    let userMessage, messageType
    if (isSuccessResponse(resp)) {
      messageType = ALERT_TYPE_SUCCESS
      userMessage = "You have successfully added the course to your cart"
    } else {
      messageType = ALERT_TYPE_DANGER
      userMessage = `Something went wrong trying to add course to cart. Please contact support at ${
        SETTINGS.support_email
      }.`
    }
    addUserNotification({
      "add-product-status": {
        type:  messageType,
        props: {
          text: userMessage
        }
      }
    })
    this.setState({ upgradeEnrollmentDialogVisibility: false })
  }
  toggleUpgradeDialogVisibility = () => {
    const { upgradeEnrollmentDialogVisibility } = this.state
    this.setState({
      upgradeEnrollmentDialogVisibility: !upgradeEnrollmentDialogVisibility
    })
  }

  renderUpgradeEnrollmentDialog() {
    const { upgradeEnrollmentDialogVisibility } = this.state
    return (
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
            <div className="col-2">$1000</div>
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
              <button
                onClick={this.addItemToBasket.bind(this)}
                className="btn btn-primary btn-gradient-red"
              >
                Continue
              </button>
            </div>
          </div>
          <div className="cancel-link">{this.getEnrollmentForm()}</div>
        </ModalBody>
      </Modal>
    )
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
            {SETTINGS.features.upgrade_dialog
              ? this.renderUpgradeEnrollmentDialog()
              : null}
          </Fragment>
        )}
      </Loader>
    )
  }
}

const addProductToBasket = (user: number, productId: number) =>
  mutateAsync(basket.addProductToBasketMutation(user, productId))

const mapDispatchToProps = {
  addProductToBasket,
  addUserNotification
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
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(ProductDetailEnrollApp)
