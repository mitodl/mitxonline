// @flow
/* global SETTINGS:false */
import React from "react"
import DocumentTitle from "react-document-title"
import { connect } from "react-redux"
import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { mutateAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { pathOr } from "ramda"
import posthog from "posthog-js"
import Loader from "../../components/Loader"
import { DASHBOARD_PAGE_TITLE } from "../../constants"
import {
  enrollmentsSelector,
  enrollmentsQuery,
  enrollmentsQueryKey,
  programEnrollmentsQuery,
  programEnrollmentsSelector,
  deactivateEnrollmentMutation,
  courseEmailsSubscriptionMutation
} from "../../lib/queries/enrollment"
import users, { currentUserSelector } from "../../lib/queries/users"
import { addUserNotification } from "../../actions"
import { ProgramEnrollmentDrawer } from "../../components/ProgramEnrollmentDrawer"
// $FlowFixMe
import { Modal, ModalHeader, ModalBody } from "reactstrap"
import { checkFeatureFlag } from "../../lib/util"

import EnrolledCourseList from "../../components/EnrolledCourseList"
import EnrolledProgramList from "../../components/EnrolledProgramList"

import AddlProfileFieldsForm from "../../components/forms/AddlProfileFieldsForm"

import type { RunEnrollment, ProgramEnrollment } from "../../flow/courseTypes"
import type { User } from "../../flow/authTypes"
import type { Country } from "../../flow/authTypes"
import queries from "../../lib/queries"

// this needs pretty drastic cleanup but not until the program bits are refactored
// to not depend on the props coming from here
type DashboardPageProps = {
  enrollments: RunEnrollment[],
  programEnrollments: ProgramEnrollment[],
  currentUser: User,
  isLoading: boolean,
  deactivateEnrollment: (enrollmentId: number) => Promise<any>,
  courseEmailsSubscription: (
    enrollmentId: number,
    emailsSubscription: string
  ) => Promise<any>,
  updateAddlFields: (currentUser: User) => Promise<any>,
  addUserNotification: Function,
  closeDrawer: Function,
  forceRequest: Function | null,
  countries: Array<Country>
}

const DashboardTab = {
  courses:  "courses",
  programs: "programs"
}

type DashboardPageState = {
  programDrawerVisibility: boolean,
  programDrawerEnrollments: ProgramEnrollment | null,
  currentTab: string,
  showAddlProfileFieldsModal: boolean,
  destinationUrl: string
}

export class DashboardPage extends React.Component<
  DashboardPageProps,
  DashboardPageState
> {
  state = {
    programDrawerVisibility:    false,
    programDrawerEnrollments:   null,
    currentTab:                 DashboardTab.courses,
    showAddlProfileFieldsModal: false,
    destinationUrl:             ""
  }

  componentDidMount() {
    const { currentUser } = this.props

    // Identify the user to PostHog using their global_id (GUID) if available
    if (currentUser && currentUser.global_id && SETTINGS.posthog_api_host) {
      posthog.identify(currentUser.global_id, {
        email:       currentUser.email,
        name:        currentUser.name,
        user_id:     currentUser.id,
        environment: SETTINGS.environment
      })

      // Wait a short time for PostHog to process the identify call before checking feature flags
      setTimeout(() => {
        try {
          // Check feature flag and redirect if enabled
          if (currentUser.global_id) {
            const flagEnabled = checkFeatureFlag(
              "redirect-to-learn-dashboard",
              currentUser.global_id
            )

            if (flagEnabled) {
              window.location.href =
                SETTINGS.mit_learn_dashboard_url ||
                "https://learn.mit.edu/dashboard"
              return
            }
          }
        } catch (error) {
          console.warn("Feature flag check failed:", error)
        }
      }, 500) // Wait 500ms for PostHog to process the identify call
    }
  }

  toggleDrawer(enrollment: any) {
    this.setState({
      programDrawerEnrollments: enrollment,
      programDrawerVisibility:  !this.state.programDrawerVisibility
    })
  }

  updateDrawerEnrollments(enrollment: any) {
    const { programDrawerEnrollments } = this.state

    if (
      programDrawerEnrollments !== null &&
      programDrawerEnrollments.program &&
      programDrawerEnrollments.program.id === enrollment.program.id
    ) {
      this.setState({
        programDrawerEnrollments: enrollment
      })
    }
  }

  toggleTab(tab: string) {
    if (tab === DashboardTab.courses || tab === DashboardTab.programs) {
      this.setState({ currentTab: tab })
    }
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

    const { currentUser } = this.props

    if (
      currentUser &&
      currentUser.legal_address &&
      currentUser.legal_address.country !== "" &&
      currentUser.legal_address.country !== null &&
      currentUser.user_profile &&
      currentUser.user_profile.year_of_birth !== "" &&
      currentUser.user_profile.year_of_birth !== null
    ) {
      return
    }

    ev.preventDefault()

    this.setState({
      destinationUrl:             url,
      showAddlProfileFieldsModal: true
    })
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

  renderCurrentTab() {
    const { enrollments, programEnrollments, forceRequest } = this.props

    if (this.state.currentTab === DashboardTab.programs) {
      if (programEnrollments.length === 0) {
        this.setState({ currentTab: DashboardTab.courses })
      } else {
        return (
          <div>
            <h2 className="hide-element">Programs</h2>
            <EnrolledProgramList
              key={"enrolled-programs"}
              enrollments={programEnrollments}
              toggleDrawer={this.toggleDrawer.bind(this)}
              onUpdateDrawerEnrollment={this.updateDrawerEnrollments.bind(this)}
              onUnenroll={forceRequest}
            ></EnrolledProgramList>
          </div>
        )
      }
    }

    return (
      <div>
        <h2 className="hide-element">My Courses</h2>
        <EnrolledCourseList
          key={"enrolled-courses"}
          enrollments={enrollments}
          redirectToCourseHomepage={this.redirectToCourseHomepage.bind(this)}
          onUnenroll={forceRequest}
        ></EnrolledCourseList>
      </div>
    )
  }

  renderAddlProfileFieldsModal() {
    const { currentUser, countries } = this.props
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
              <p>We need more information about you before you can start.</p>
            </div>
          </div>

          <AddlProfileFieldsForm
            onSubmit={this.saveProfile.bind(this)}
            onCancel={() => this.toggleAddlProfileFieldsModal()}
            user={currentUser}
            countries={countries}
          ></AddlProfileFieldsForm>
        </ModalBody>
      </Modal>
    )
  }

  render() {
    const { isLoading, programEnrollments, forceRequest } = this.props

    const myCourseClasses = `dash-tab${
      this.state.currentTab === DashboardTab.courses ? " active" : ""
    }`
    const programsClasses = `dash-tab${
      this.state.currentTab === DashboardTab.programs ? " active" : ""
    }`
    const programEnrollmentsLength = programEnrollments ?
      programEnrollments.length :
      0

    return (
      <DocumentTitle title={`${SETTINGS.site_name} | ${DASHBOARD_PAGE_TITLE}`}>
        <>
          <div role="banner" className="std-page-header">
            <h1>{DASHBOARD_PAGE_TITLE}</h1>
          </div>
          <div className="dashboard std-page-body container">
            <Loader isLoading={isLoading}>
              <nav className="tabs d-flex" aria-controls="enrollment-items">
                {programEnrollmentsLength === 0 ? (
                  <>
                    <button
                      className={myCourseClasses}
                      onClick={() => this.toggleTab(DashboardTab.courses)}
                    >
                      My Courses
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      className={myCourseClasses}
                      onClick={() => this.toggleTab(DashboardTab.courses)}
                    >
                      My Courses
                    </button>
                    <button
                      className={programsClasses}
                      onClick={() => this.toggleTab(DashboardTab.programs)}
                    >
                      My Programs
                    </button>
                  </>
                )}
              </nav>
              <div id="enrollment-items" className="enrolled-items">
                {this.renderCurrentTab()}
              </div>

              <ProgramEnrollmentDrawer
                isHidden={this.state.programDrawerVisibility}
                enrollment={this.state.programDrawerEnrollments}
                showDrawer={() =>
                  this.setState({ programDrawerVisibility: false })
                }
                redirectToCourseHomepage={this.redirectToCourseHomepage}
                onUnenroll={forceRequest}
              ></ProgramEnrollmentDrawer>

              {this.renderAddlProfileFieldsModal()}
            </Loader>
          </div>
        </>
      </DocumentTitle>
    )
  }
}

const mapStateToProps = createStructuredSelector({
  enrollments:        enrollmentsSelector,
  programEnrollments: programEnrollmentsSelector,
  currentUser:        currentUserSelector,
  isLoading:          pathOr(true, ["queries", enrollmentsQueryKey, "isPending"]),
  countries:          queries.users.countriesSelector
})

const mapPropsToConfig = () => [
  enrollmentsQuery(),
  programEnrollmentsQuery(),
  queries.users.countriesQuery()
]

const deactivateEnrollment = (enrollmentId: number) =>
  mutateAsync(deactivateEnrollmentMutation(enrollmentId))

const courseEmailsSubscription = (
  enrollmentId: number,
  emailsSubscription: string
) =>
  mutateAsync(
    courseEmailsSubscriptionMutation(enrollmentId, emailsSubscription)
  )

const updateAddlFields = (currentUser: User) => {
  const updatedUser = {
    name:          currentUser.name,
    email:         currentUser.email,
    legal_address: currentUser.legal_address,
    user_profile:  currentUser.user_profile
  }

  return mutateAsync(users.editProfileMutation(updatedUser))
}

const mapDispatchToProps = {
  deactivateEnrollment,
  courseEmailsSubscription,
  updateAddlFields,
  addUserNotification
}

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(DashboardPage)
