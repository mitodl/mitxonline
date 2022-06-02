// @flow
/* global SETTINGS:false */
import React from "react"
import { connect } from "react-redux"
import { Formik, Form, Field } from "formik"
import {
  Dropdown,
  DropdownToggle,
  DropdownMenu,
  DropdownItem,
  Button,
  Modal,
  ModalHeader,
  ModalBody
} from "reactstrap"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connectRequest, mutateAsync } from "redux-query"
import { partial, pathOr, without } from "ramda"
import moment from "moment"

import { ALERT_TYPE_DANGER, ALERT_TYPE_SUCCESS } from "../constants"
import {
  enrollmentSelector,
  enrollmentQuery,
  enrollmentQueryKey,
  deactivateEnrollmentMutation,
  courseEmailsSubscriptionMutation
} from "../lib/queries/enrollment"
import { currentUserSelector } from "../lib/queries/users"
import { isLinkableCourseRun, generateStartDateText } from "../lib/courseApi"
import {
  formatPrettyDateTimeAmPmTz,
  isSuccessResponse,
  parseDateString
} from "../lib/util"
import { addUserNotification } from "../actions"
import { EnrollmentRoleTag } from "./EnrollmentRoleTag"

import type { RunEnrollment } from "../flow/courseTypes"
import type { CurrentUser } from "../flow/authTypes"

type EnrolledItemCardProps = {
  enrollment: RunEnrollment,
  currentUser: CurrentUser,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  addUserNotification: Function
}

type EnrolledItemCardState = {
  submittingEnrollmentId: number | null,
  activeMenuIds: number[],
  emailSettingsModalVisibility: boolean[],
  verifiedUnenrollmentModalVisibility: boolean[]
}

export class EnrolledItemCard extends React.Component<
  EnrolledItemCardProps,
  EnrolledItemCardState
> {
  state = {
    submittingEnrollmentId:              null,
    activeMenuIds:                       [],
    emailSettingsModalVisibility:        [],
    verifiedUnenrollmentModalVisibility: []
  }

  toggleEmailSettingsModalVisibility = (enrollmentId: number) => {
    const { emailSettingsModalVisibility } = this.state
    let isOpen = false
    if (emailSettingsModalVisibility[enrollmentId] === undefined) {
      isOpen = true
    } else {
      isOpen = !emailSettingsModalVisibility[enrollmentId]
    }
    emailSettingsModalVisibility[enrollmentId] = isOpen
    this.setState({
      emailSettingsModalVisibility: emailSettingsModalVisibility
    })
  }

  toggleVerifiedUnenrollmentModalVisibility = (enrollmentId: number) => {
    const { verifiedUnenrollmentModalVisibility } = this.state
    let isOpen = false
    if (verifiedUnenrollmentModalVisibility[enrollmentId] === undefined) {
      isOpen = true
    } else {
      isOpen = !verifiedUnenrollmentModalVisibility[enrollmentId]
    }
    verifiedUnenrollmentModalVisibility[enrollmentId] = isOpen
    this.setState({
      verifiedUnenrollmentModalVisibility: verifiedUnenrollmentModalVisibility
    })
  }

  isActiveMenuId(itemId: number): boolean {
    return !!this.state.activeMenuIds.find(id => id === itemId)
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

  async onDeactivate(enrollment: RunEnrollment) {
    const { deactivateEnrollment, addUserNotification } = this.props

    if (enrollment.enrollment_mode === "verified") {
      console.log("enrollment is paid, can't unenroll")
      this.toggleVerifiedUnenrollmentModalVisibility(enrollment.id)
      return
    }

    this.setState({ submittingEnrollmentId: enrollment.id })
    try {
      const resp = await deactivateEnrollment(enrollment.id)
      let userMessage, messageType
      if (isSuccessResponse(resp)) {
        messageType = ALERT_TYPE_SUCCESS
        userMessage = `You have been successfully unenrolled from ${enrollment.run.title}.`
      } else {
        messageType = ALERT_TYPE_DANGER
        userMessage = `Something went wrong with your request to unenroll. Please contact support at ${SETTINGS.support_email}.`
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
    this.toggleEmailSettingsModalVisibility(payload.enrollmentId)
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
        userMessage = `You have been successfully ${message} course ${payload.courseNumber} emails.`
      } else {
        messageType = ALERT_TYPE_DANGER
        userMessage = `Something went wrong with your request to course ${payload.courseNumber} emails subscription. Please contact support at ${SETTINGS.support_email}.`
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
    let isOpen = false
    if (emailSettingsModalVisibility[enrollment.id] !== undefined) {
      isOpen = emailSettingsModalVisibility[enrollment.id]
    }

    return (
      <Modal
        id={`enrollment-${enrollment.id}-modal`}
        className="text-center"
        isOpen={isOpen}
        toggle={() => this.toggleEmailSettingsModalVisibility(enrollment.id)}
      >
        <ModalHeader
          toggle={() => this.toggleEmailSettingsModalVisibility(enrollment.id)}
        >
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
                <Button
                  onClick={() =>
                    this.toggleEmailSettingsModalVisibility(enrollment.id)
                  }
                >
                  Cancel
                </Button>
              </Form>
            )}
          />
        </ModalBody>
      </Modal>
    )
  }

  renderVerifiedUnenrollmentModal(enrollment: RunEnrollment) {
    const { verifiedUnenrollmentModalVisibility } = this.state
    let isOpen = false
    if (verifiedUnenrollmentModalVisibility[enrollment.id] !== undefined) {
      isOpen = verifiedUnenrollmentModalVisibility[enrollment.id]
    }

    return (
      <Modal
        id={`verified-unenrollment-${enrollment.id}-modal`}
        className="text-center"
        isOpen={isOpen}
        toggle={() =>
          this.toggleVerifiedUnenrollmentModalVisibility(enrollment.id)
        }
      >
        <ModalHeader
          toggle={() =>
            this.toggleVerifiedUnenrollmentModalVisibility(enrollment.id)
          }
        >
          Unenroll From {enrollment.run.course_number}
        </ModalHeader>
        <ModalBody>
          <p>
            You are enrolled in the certificate track for{" "}
            {enrollment.run.course_number} {enrollment.run.title}. You can't
            unenroll from this course from My Courses.
          </p>

          <p>
            To unenroll, please{" "}
            <a href="https://mitxonline.zendesk.com/hc/en-us/requests/new">
              contact customer support
            </a>{" "}
            for assistance.
          </p>
        </ModalBody>
      </Modal>
    )
  }

  render() {
    const {
      enrollment,
      currentUser,
      deactivateEnrollment,
      addUserNotification
    } = this.props

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
    const startDateDescription = generateStartDateText(enrollment.run)
    const onUnenrollClick = partial(this.onDeactivate.bind(this), [enrollment])
    const courseId = enrollment.run.course_number
    const enrollmentMode = enrollment.enrollment_mode
    const pageLocation = enrollment.run.page
    // certLocation is not used yet, just here to test layout
    const certLocation = false

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
            <div className="d-flex justify-content-between align-content-start flex-nowrap w-100 enrollment-mode-container">
              <EnrollmentRoleTag
                enrollmentMode={enrollmentMode}
              ></EnrollmentRoleTag>
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
                    >
                      Unenroll
                    </DropdownItem>
                    {this.renderVerifiedUnenrollmentModal(enrollment)}
                  </span>
                  <span id="subscribeButtonWrapper">
                    <DropdownItem
                      className="unstyled d-block"
                      onClick={() =>
                        this.toggleEmailSettingsModalVisibility(enrollment.id)
                      }
                    >
                      Email Settings
                    </DropdownItem>
                    {this.renderEmailSettingsDialog(enrollment)}
                  </span>
                </DropdownMenu>
              </Dropdown>
            </div>

            <div className="d-flex justify-content-between align-content-start flex-nowrap mb-3">
              <h2 className="my-0 mr-3">{title}</h2>
            </div>
            <div className="detail">
              {courseId} |{" "}
              {startDateDescription !== null && startDateDescription.active ? (
                <span>Starts - {startDateDescription.datestr}</span>
              ) : (
                <span>
                  {startDateDescription === null ? null : (
                    <span>
                      <strong>Active</strong> from{" "}
                      {startDateDescription.datestr}
                    </span>
                  )}
                </span>
              )}
              <div className="enrollment-extra-links d-flex">
                {pageLocation ? (
                  <a href={pageLocation.page_url}>Course details</a>
                ) : null}
                {certLocation ? (
                  <a href={certLocation}>View certificate</a>
                ) : null}
                {enrollment.run.products.length > 0 &&
                enrollmentMode === "audit" ? (
                    <form
                      action="/cart/add/"
                      method="get"
                      className="text-center ml-auto"
                    >
                      <input
                        type="hidden"
                        name="product_id"
                        value={enrollment.run.products[0].id}
                      />
                      <button
                        type="submit"
                        className="btn btn-primary btn-gradient-red"
                      >
                      Get Certificate
                      </button>
                    </form>
                  ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }
}

export default EnrolledItemCard
