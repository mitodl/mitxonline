// @flow
/* global SETTINGS:false */
import React from "react"
import DocumentTitle from "react-document-title"
import { connect } from "react-redux"
import { Formik, Form, Field } from "formik"
import {
  Tooltip,
  Dropdown,
  DropdownToggle,
  DropdownMenu,
  DropdownItem,
  Modal,
  ModalHeader,
  ModalBody,
  Button
} from "reactstrap"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connectRequest, mutateAsync } from "redux-query"
import { partial, pathOr, without } from "ramda"
import moment from "moment"

import Loader from "../../components/Loader"
import {
  ALERT_TYPE_DANGER,
  ALERT_TYPE_SUCCESS,
  DASHBOARD_PAGE_TITLE
} from "../../constants"
import {
  enrollmentsSelector,
  enrollmentsQuery,
  enrollmentsQueryKey,
  deactivateEnrollmentMutation,
  courseEmailsSubscriptionMutation
} from "../../lib/queries/enrollment"
import { currentUserSelector } from "../../lib/queries/users"
import {
  isLinkableCourseRun,
  isWithinEnrollmentPeriod
} from "../../lib/courseApi"
import {
  formatPrettyDateTimeAmPmTz,
  isSuccessResponse,
  parseDateString
} from "../../lib/util"
import { routes } from "../../lib/urls"
import { addUserNotification } from "../../actions"

import type { RunEnrollment } from "../../flow/courseTypes"
import type { CurrentUser } from "../../flow/authTypes"

type DashboardPageProps = {
  enrollments: RunEnrollment[],
  currentUser: CurrentUser,
  isLoading: boolean,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  addUserNotification: Function
}

type DashboardPageState = {
  submittingEnrollmentId: number | null,
  activeMenuIds: number[],
  activeEnrollMsgIds: number[],
  emailSettingsModalVisibility: boolean
}

export class DashboardPage extends React.Component<
  DashboardPageProps,
  DashboardPageState
> {
  state = {
    submittingEnrollmentId:       null,
    activeMenuIds:                [],
    activeEnrollMsgIds:           [],
    emailSettingsModalVisibility: false
  }

  toggleEmailSettingsModalVisibility = () => {
    const { emailSettingsModalVisibility } = this.state
    this.setState({
      emailSettingsModalVisibility: !emailSettingsModalVisibility
    })
  }

  isActiveMenuId(itemId: number): boolean {
    return !!this.state.activeMenuIds.find(id => id === itemId)
  }

  isActiveEnrollMsgId(itemId: number): boolean {
    return !!this.state.activeEnrollMsgIds.find(id => id === itemId)
  }

  toggleActiveMenuId(itemId: number) {
    return () => {
      const isActive = this.isActiveMenuId(itemId)
      this.setState({
        activeMenuIds: isActive
          ? without([itemId], this.state.activeMenuIds)
          : [...this.state.activeMenuIds, itemId]
      })
    }
  }

  toggleActiveEnrollMsgId(itemId: number) {
    return () => {
      const isActive = this.isActiveEnrollMsgId(itemId)
      this.setState({
        activeEnrollMsgIds: isActive
          ? without([itemId], this.state.activeEnrollMsgIds)
          : [...this.state.activeEnrollMsgIds, itemId]
      })
    }
  }

  async onDeactivate(enrollment: RunEnrollment) {
    const { deactivateEnrollment, addUserNotification } = this.props
    this.setState({ submittingEnrollmentId: enrollment.id })
    try {
      const resp = await deactivateEnrollment(enrollment.id)
      let userMessage, messageType
      if (isSuccessResponse(resp)) {
        messageType = ALERT_TYPE_SUCCESS
        userMessage = `You have been successfully unenrolled from ${
          enrollment.run.title
        }.`
      } else {
        messageType = ALERT_TYPE_DANGER
        userMessage = `Something went wrong with your request to unenroll. Please contact support at ${
          SETTINGS.support_email
        }.`
      }
      addUserNotification({
        "unenroll-status": {
          type:  messageType,
          props: {
            text: userMessage
          }
        }
      })
      // Scroll to the top of the page to make sure the user sees the message
      window.scrollTo(0, 0)
    } finally {
      this.setState({ submittingEnrollmentId: null })
    }
  }

  async onSubmit(payload: Object) {
    const { courseEmailsSubscription, addUserNotification } = this.props
    this.setState({ submittingEnrollmentId: payload.enrollmentId })
    this.toggleEmailSettingsModalVisibility()
    try {
      const resp = await courseEmailsSubscription(
        payload.enrollmentId,
        payload.subscribeEmails
      )

      let userMessage, messageType
      if (isSuccessResponse(resp)) {
        const message = payload.subscribeEmails
          ? "subscribed to"
          : "unsubscribed from"
        messageType = ALERT_TYPE_SUCCESS
        userMessage = `You have been successfully ${message} course ${
          payload.courseNumber
        } emails.`
      } else {
        messageType = ALERT_TYPE_DANGER
        userMessage = `Something went wrong with your request to course ${
          payload.courseNumber
        } emails subscription. Please contact support at ${
          SETTINGS.support_email
        }.`
      }
      addUserNotification({
        "subscription-status": {
          type:  messageType,
          props: {
            text: userMessage
          }
        }
      })
      // Scroll to the top of the page to make sure the user sees the message
      window.scrollTo(0, 0)
    } finally {
      this.setState({ submittingEnrollmentId: null })
    }
  }

  renderEmailSettingsDialog(enrollment: RunEnrollment) {
    const { emailSettingsModalVisibility } = this.state
    return (
      <Modal
        className="text-center"
        isOpen={emailSettingsModalVisibility}
        toggle={this.toggleEmailSettingsModalVisibility}
      >
        <ModalHeader toggle={this.toggleEmailSettingsModalVisibility}>
          Email Settings for {enrollment.run.course_number}
        </ModalHeader>
        <ModalBody>
          <Formik
            onSubmit={this.onSubmit.bind(this)}
            initialValues={{
              subscribeEmails: enrollment.edx_emails_subscription,
              enrollmentId:    enrollment.id,
              courseNumber:    enrollment.run.course_number
            }}
            render={({ values }) => (
              <Form className="text-center">
                <section>
                  <Field
                    type="hidden"
                    name="enrollmentId"
                    value={values.enrollmentId}
                  />
                  <Field
                    type="hidden"
                    name="courseNumber"
                    value={values.courseNumber}
                  />
                  <Field
                    type="checkbox"
                    name="subscribeEmails"
                    checked={values.subscribeEmails}
                  />{" "}
                  <label check>Receive course emails</label>
                </section>
                <Button type="submit" color="success">
                  Save Settings
                </Button>{" "}
                <Button onClick={this.toggleEmailSettingsModalVisibility}>
                  Cancel
                </Button>
              </Form>
            )}
          />
        </ModalBody>
      </Modal>
    )
  }

  renderEnrolledItemCard(enrollment: RunEnrollment) {
    const { currentUser } = this.props
    const { submittingEnrollmentId } = this.state

    let startDate, startDateDescription, onUnenrollClick, unenrollEnabled
    const title = isLinkableCourseRun(enrollment.run, currentUser) ? (
      <a
        href={enrollment.run.courseware_url}
        target="_blank"
        rel="noopener noreferrer"
      >
        {enrollment.run.course.title}
      </a>
    ) : (
      enrollment.run.course.title
    )
    if (enrollment.run.start_date) {
      const now = moment()
      startDate = parseDateString(enrollment.run.start_date)
      const formattedStartDate = formatPrettyDateTimeAmPmTz(startDate)
      startDateDescription = now.isBefore(startDate) ? (
        <span>Starts - {formattedStartDate}</span>
      ) : (
        <span>
          <strong>Active</strong> from {formattedStartDate}
        </span>
      )
    }
    if (isWithinEnrollmentPeriod(enrollment.run)) {
      onUnenrollClick = partial(this.onDeactivate.bind(this), [enrollment])
      unenrollEnabled = true
    } else {
      onUnenrollClick = () => {}
      unenrollEnabled = false
    }

    return (
      <div
        className="enrolled-item container card p-md-3 mb-4 rounded-0"
        key={enrollment.run.id}
      >
        <div className="row flex-grow-1">
          {enrollment.run.course.feature_image_src && (
            <div className="col-12 col-md-auto px-0 px-md-3">
              <div className="img-container">
                <img
                  src={enrollment.run.course.feature_image_src}
                  alt="Preview image"
                />
              </div>
            </div>
          )}
          <div className="col-12 col-md px-3 py-3 py-md-0">
            <div className="d-flex justify-content-between align-content-start flex-nowrap mb-3">
              <h2 className="my-0 mr-3">{title}</h2>
              <Dropdown
                isOpen={this.isActiveMenuId(enrollment.id)}
                toggle={this.toggleActiveMenuId(enrollment.id).bind(this)}
                id={`enrollmentDropdown-${enrollment.id}`}
              >
                <DropdownToggle className="d-inline-flex unstyled dot-menu">
                  <i className="material-icons">more_vert</i>
                </DropdownToggle>
                <DropdownMenu right>
                  <span id={`unenrollButtonWrapper-${enrollment.id}`}>
                    <DropdownItem
                      className="unstyled d-block"
                      onClick={onUnenrollClick}
                      {...(!unenrollEnabled ||
                      enrollment.id === submittingEnrollmentId
                        ? { disabled: true }
                        : {})}
                    >
                      Unenroll
                    </DropdownItem>
                  </span>
                  <span id="subscribeButtonWrapper">
                    <DropdownItem
                      className="unstyled d-block"
                      onClick={() => this.toggleEmailSettingsModalVisibility()}
                    >
                      Email Settings
                    </DropdownItem>
                    {this.renderEmailSettingsDialog(enrollment)}
                  </span>
                  {!unenrollEnabled && (
                    <Tooltip
                      delay={0}
                      placement="bottom-end"
                      target={`unenrollButtonWrapper-${enrollment.id}`}
                      container={`enrollmentDropdown-${enrollment.id}`}
                      className="unenroll-denied-msg"
                      isOpen={this.isActiveEnrollMsgId(enrollment.id)}
                      toggle={this.toggleActiveEnrollMsgId(enrollment.id).bind(
                        this
                      )}
                    >
                      The enrollment period for this course has ended. If you'd
                      like to unenroll, please contact support.
                    </Tooltip>
                  )}
                </DropdownMenu>
              </Dropdown>
            </div>
            <div className="detail">{startDateDescription}</div>
          </div>
        </div>
      </div>
    )
  }

  render() {
    const { enrollments, isLoading } = this.props

    return (
      <DocumentTitle title={`${SETTINGS.site_name} | ${DASHBOARD_PAGE_TITLE}`}>
        <div className="std-page-body dashboard container">
          <Loader isLoading={isLoading}>
            <h1>My Courses</h1>
            <div className="enrolled-items">
              {enrollments && enrollments.length > 0 ? (
                enrollments.map(this.renderEnrolledItemCard.bind(this))
              ) : (
                <div className="card no-enrollments p-3 p-md-5 rounded-0">
                  <h2>Enroll Now</h2>
                  <p>
                    You are not enrolled in any courses yet. Please{" "}
                    <a href={routes.root}>browse our courses</a>.
                  </p>
                </div>
              )}
            </div>
          </Loader>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  enrollments: enrollmentsSelector,
  currentUser: currentUserSelector,
  isLoading:   pathOr(true, ["queries", enrollmentsQueryKey, "isPending"])
})

const mapPropsToConfig = () => [enrollmentsQuery()]

const deactivateEnrollment = (enrollmentId: number) =>
  mutateAsync(deactivateEnrollmentMutation(enrollmentId))

const courseEmailsSubscription = (
  enrollmentId: number,
  emailsSubscription: string
) =>
  mutateAsync(
    courseEmailsSubscriptionMutation(enrollmentId, emailsSubscription)
  )

const mapDispatchToProps = {
  deactivateEnrollment,
  courseEmailsSubscription,
  addUserNotification
}

export default compose(
  connect(
    mapStateToProps,
    mapDispatchToProps
  ),
  connectRequest(mapPropsToConfig)
)(DashboardPage)
