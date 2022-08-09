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
  programEnrollmentsQuery,
  programEnrollmentsQueryKey,
  programEnrollmentsSelector,
  deactivateEnrollmentMutation,
  courseEmailsSubscriptionMutation
} from "../../lib/queries/enrollment"
import { currentUserSelector } from "../../lib/queries/users"
import { isLinkableCourseRun } from "../../lib/courseApi"
import {
  formatPrettyDateTimeAmPmTz,
  isSuccessResponse,
  parseDateString
} from "../../lib/util"
import { routes } from "../../lib/urls"
import { addUserNotification } from "../../actions"
import { EnrolledItemCard } from "../../components/EnrolledItemCard"
import { ProgramEnrollmentCard } from "../../components/ProgramEnrollmentCard"
import { ProgramEnrollmentDrawer } from "../../components/ProgramEnrollmentDrawer"

import type { RunEnrollment, ProgramEnrollment } from "../../flow/courseTypes"
import type { CurrentUser } from "../../flow/authTypes"

type DashboardPageProps = {
  enrollments: RunEnrollment[],
  programEnrollments: ProgramEnrollment[],
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
  emailSettingsModalVisibility: boolean[],
  programDrawerVisibility: boolean,
  programDrawerEnrollments: any[],
}

export class DashboardPage extends React.Component<
  DashboardPageProps,
  DashboardPageState
> {
  state = {
    submittingEnrollmentId:       null,
    activeMenuIds:                [],
    emailSettingsModalVisibility: [],
    programDrawerVisibility:      false,
    programDrawerEnrollments:     [],
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

  toggleDrawer(enrollments: any) {
    this.setState({
      programDrawerEnrollments: enrollments,
      programDrawerVisibility:  !this.state.programDrawerVisibility
    })
  }

  async onDeactivate(enrollment: RunEnrollment) {
    const { deactivateEnrollment, addUserNotification } = this.props
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

  renderEnrolledItemCard(enrollment: RunEnrollment) {
    const {
      programEnrollments,
      currentUser,
      deactivateEnrollment,
      courseEmailsSubscription,
      addUserNotification,
    } = this.props

    if (programEnrollments) {
      const enrollmentMatches = programEnrollments.map(programEnrollment => programEnrollment.enrollments.some(elem => elem.id === enrollment.id))

      if (enrollmentMatches.includes(true)) {
        return null
      }
    }

    return (
      <EnrolledItemCard
        key={enrollment.id}
        enrollment={enrollment}
        currentUser={currentUser}
        deactivateEnrollment={deactivateEnrollment}
        courseEmailsSubscription={courseEmailsSubscription}
        addUserNotification={addUserNotification}
      ></EnrolledItemCard>
    )
  }

  render() {
    const {
      enrollments,
      programEnrollments,
      isLoading,
      currentUser,
      deactivateEnrollment,
      courseEmailsSubscription,
      addUserNotification,
    } = this.props

    return (
      <DocumentTitle title={`${SETTINGS.site_name} | ${DASHBOARD_PAGE_TITLE}`}>
        <div className="std-page-body dashboard container">
          <Loader isLoading={isLoading}>
            <h1>My Courses</h1>
            <div className="enrolled-items">
              {programEnrollments && programEnrollments.length > 0 ? (
                programEnrollments.map(programEnrollment => (
                  <ProgramEnrollmentCard
                    key={programEnrollment.program.readable_id}
                    enrollment={programEnrollment}
                    currentUser={currentUser}
                    deactivateEnrollment={deactivateEnrollment}
                    courseEmailsSubscription={courseEmailsSubscription}
                    addUserNotification={addUserNotification}
                    showDrawer={this.toggleDrawer.bind(this)}
                  ></ProgramEnrollmentCard>
                ))) : null}
              {enrollments && enrollments.length > 0 ? (
                enrollments.map(enrollment => this.renderEnrolledItemCard(enrollment))
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
            <ProgramEnrollmentDrawer
              currentUser={currentUser}
              deactivateEnrollment={deactivateEnrollment}
              courseEmailsSubscription={courseEmailsSubscription}
              addUserNotification={addUserNotification}
              isHidden={this.state.programDrawerVisibility}
              enrollments={this.state.programDrawerEnrollments}
              showDrawer={() => this.setState({programDrawerVisibility: false})}></ProgramEnrollmentDrawer>
          </Loader>
        </div>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  enrollments:        enrollmentsSelector,
  programEnrollments: programEnrollmentsSelector,
  currentUser:        currentUserSelector,
  isLoading:          pathOr(true, ["queries", enrollmentsQueryKey, "isPending"])
})

const mapPropsToConfig = () => [enrollmentsQuery(), programEnrollmentsQuery()]

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
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(DashboardPage)
