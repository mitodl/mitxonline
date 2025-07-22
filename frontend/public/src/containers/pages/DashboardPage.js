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

export class DashboardPage extends React.PureComponent<
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

  constructor(props: DashboardPageProps) {
    super(props)
    
    // Bind methods to avoid creating new functions on every render
    this.toggleDrawer = this.toggleDrawer.bind(this)
    this.updateDrawerEnrollments = this.updateDrawerEnrollments.bind(this)
    this.toggleTab = this.toggleTab.bind(this)
    this.toggleAddlProfileFieldsModal = this.toggleAddlProfileFieldsModal.bind(this)
    this.redirectToCourseHomepage = this.redirectToCourseHomepage.bind(this)
    this.saveProfile = this.saveProfile.bind(this)
    this.renderCurrentTab = this.renderCurrentTab.bind(this)
    this.renderAddlProfileFieldsModal = this.renderAddlProfileFieldsModal.bind(this)
    
    // Cache for computed values
    this._tabClassesCache = null
    this._lastCurrentTab = null
  }

  componentWillUnmount() {
    // Clean up cache references to prevent memory leaks
    this._tabClassesCache = null
    this._lastCurrentTab = null
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
      enrollment?.program &&
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
      try {
        window.open(target, "_blank")
      } catch (error) {
        console.error("Failed to open window:", error)
        // Fallback to location.href if popup is blocked
        window.location.href = target
      }
    }
  }

  // Memoize tab classes computation to avoid recalculation on every render
  getTabClasses = () => {
    const { currentTab } = this.state
    
    // Return cached result if currentTab hasn't changed
    if (this._lastCurrentTab === currentTab && this._tabClassesCache) {
      return this._tabClassesCache
    }
    
    const myCourseClasses = `dash-tab${
      currentTab === DashboardTab.courses ? " active" : ""
    }`
    const programsClasses = `dash-tab${
      currentTab === DashboardTab.programs ? " active" : ""
    }`
    
    const classes = { myCourseClasses, programsClasses }
    
    // Cache the result
    this._tabClassesCache = classes
    this._lastCurrentTab = currentTab
    
    return classes
  }

  // Optimize user profile validation
  shouldShowProfileModal = (currentUser: User): boolean => {
    return !(
      currentUser &&
      currentUser.legal_address &&
      currentUser.legal_address.country !== "" &&
      currentUser.legal_address.country !== null &&
      currentUser.user_profile &&
      currentUser.user_profile.year_of_birth !== "" &&
      currentUser.user_profile.year_of_birth !== null
    )
  }

  redirectToCourseHomepage(url: string, ev: any) {
    /*
    If we've got addl_field_flag, then display the extra info modal. Otherwise,
    send the learner directly to the page.
    */

    const { currentUser } = this.props

    if (!url || typeof url !== 'string') {
      console.error("Invalid URL provided to redirectToCourseHomepage:", url)
      return
    }

    if (!this.shouldShowProfileModal(currentUser)) {
      return
    }

    if (ev && typeof ev.preventDefault === 'function') {
      ev.preventDefault()
    }

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
    const { currentTab } = this.state

    // Defensive checks for data
    const safeEnrollments = enrollments || []
    const safeProgramEnrollments = programEnrollments || []

    if (currentTab === DashboardTab.programs) {
      if (safeProgramEnrollments.length === 0) {
        this.setState({ currentTab: DashboardTab.courses })
      } else {
        return (
          <div>
            <h2 className="hide-element">Programs</h2>
            <EnrolledProgramList
              key="enrolled-programs"
              enrollments={safeProgramEnrollments}
              toggleDrawer={this.toggleDrawer}
              onUpdateDrawerEnrollment={this.updateDrawerEnrollments}
              onUnenroll={forceRequest}
            />
          </div>
        )
      }
    }

    return (
      <div>
        <h2 className="hide-element">My Courses</h2>
        <EnrolledCourseList
          key="enrolled-courses"
          enrollments={safeEnrollments}
          redirectToCourseHomepage={this.redirectToCourseHomepage}
          onUnenroll={forceRequest}
        />
      </div>
    )
  }

  renderAddlProfileFieldsModal() {
    const { currentUser, countries } = this.props
    const { showAddlProfileFieldsModal } = this.state

    // Defensive check for required props
    if (!currentUser || !countries) {
      return null
    }

    return (
      <Modal
        id="upgrade-enrollment-dialog"
        className="upgrade-enrollment-modal"
        isOpen={showAddlProfileFieldsModal}
        toggle={this.toggleAddlProfileFieldsModal}
      >
        <ModalHeader
          id={`more-info-modal-${currentUser.id}`}
          toggle={this.toggleAddlProfileFieldsModal}
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
            onSubmit={this.saveProfile}
            onCancel={this.toggleAddlProfileFieldsModal}
            user={currentUser}
            countries={countries}
          />
        </ModalBody>
      </Modal>
    )
  }

  render() {
    const { isLoading, programEnrollments, forceRequest } = this.props
    
    // Use memoized tab classes computation
    const { myCourseClasses, programsClasses } = this.getTabClasses()
    
    const programEnrollmentsLength = programEnrollments ?
      programEnrollments.length :
      0

    // Create stable references for event handlers
    const handleCoursesTabClick = () => this.toggleTab(DashboardTab.courses)
    const handleProgramsTabClick = () => this.toggleTab(DashboardTab.programs)
    const handleDrawerShow = () => this.setState({ programDrawerVisibility: false })

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
                      onClick={handleCoursesTabClick}
                    >
                      My Courses
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      className={myCourseClasses}
                      onClick={handleCoursesTabClick}
                    >
                      My Courses
                    </button>
                    <button
                      className={programsClasses}
                      onClick={handleProgramsTabClick}
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
                showDrawer={handleDrawerShow}
                redirectToCourseHomepage={this.redirectToCourseHomepage}
                onUnenroll={forceRequest}
              />

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
