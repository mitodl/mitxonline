import React from "react"
import { CSSTransition, TransitionGroup } from "react-transition-group"
import { getStartDateText } from "../../lib/util"

import {
  coursesCountSelector,
  coursesSelector,
  coursesNextPageSelector,
  coursesQuery,
  coursesQueryKey
} from "../../lib/queries/catalogCourses"

import {
  programsCountSelector,
  programsSelector,
  programsNextPageSelector,
  programsQuery,
  programsQueryKey
} from "../../lib/queries/programs"

import {
  departmentsSelector,
  departmentsQuery,
  departmentsQueryKey
} from "../../lib/queries/departments"

import { createStructuredSelector } from "reselect"
import { compose } from "redux"
import { connect } from "react-redux"
import { requestAsync } from "redux-query"
import { connectRequest } from "redux-query-react"
import { pathOr } from "ramda"
import CourseLoader from "../../components/CourseLoader"
import { Match } from "react-router"

type Props = {
  coursesIsLoading: ?boolean,
  programsIsLoading: ?boolean,
  courses: ?Array<CourseDetailWithRuns>,
  programs: ?Array<Program>,
  forceRequest: () => Promise<*>,
  coursesNextPage: ?string,
  programsNextPage: ?string,
  programsCount: number,
  coursesCount: number,
  departments: ?Array<Department>,
  match: Match
}

// Department filter name for all items.
const ALL_DEPARTMENTS = "All Departments"

// Program tab name.
const PROGRAMS_TAB = "programs"

// Course tab name.
const COURSES_TAB = "courses"

const TABS = [PROGRAMS_TAB, COURSES_TAB]

export class CatalogPage extends React.Component<Props> {
  state = {
    tabSelected:                      COURSES_TAB,
    allCoursesRetrieved:              [],
    allCoursesCount:                  0,
    allProgramsRetrieved:             [],
    allProgramsCount:                 0,
    filteredCourses:                  [],
    filteredPrograms:                 [],
    filterProgramsCalled:             false,
    filterCoursesCalled:              false,
    filteredDepartments:              [],
    filterDepartmentsByTabNameCalled: false,
    selectedDepartment:               ALL_DEPARTMENTS,
    mobileFilterWindowExpanded:       false,
    items_per_row:                    3,
    courseQueryPage:                  1,
    programQueryPage:                 1,
    isLoadingMoreItems:               false,
    courseQueryIDListString:          ""
  }

  constructor(props) {
    super(props)
    this.io = null
    this.container = React.createRef(null)
    const { match } = this.props
    if (match) {
      const { tab, department } = match.params
      if (TABS.includes(tab)) {
        this.state.tabSelected = tab
      } else {
        this.state.tabSelected = COURSES_TAB
      }
      if (department) {
        this.state.selectedDepartment = department
      } else {
        this.state.selectedDepartment = ALL_DEPARTMENTS
      }
    }
  }

  componentWillUnmount() {
    if (this.io) {
      this.io.disconnect()
    }
  }

  /**
   * Callback when the bottom of the catalog is visible.
   * Retrieves more courses or programs based on the value of
   * the tabSelected state variable.
   */
  bottomOfLoadedCatalogCallback = async entries => {
    const { coursesNextPage } = this.props
    const [entry] = entries
    if (entry.isIntersecting) {
      if (this.state.tabSelected === COURSES_TAB) {
        if (
          this.state.filteredCourses.length <
            this.renderNumberOfCatalogItems() &&
          coursesNextPage
        ) {
          this.retrieveMoreCourses()
        }
      } else {
        if (
          this.state.filteredPrograms.length <
            this.renderNumberOfCatalogItems() &&
          this.state.allProgramsRetrieved.length > 0
        ) {
          // Only retrieve more programs after we have already populated allProgramsRetrieved with the initial API response,
          // and when not all programs, for the currently selected department, are currently displayed.
          this.retrieveMorePrograms()
        }
      }
    }
  }

  /**
   * Initializes many of the state variables with the responses from the programs, courses, and departments API.
   * Adds an intersection observer in order to load more catalog items when the user scrolls to the bottom of the page.
   */
  componentDidUpdate = () => {
    const {
      courses,
      coursesCount,
      coursesIsLoading,
      programsIsLoading,
      programs,
      programsCount,
      departments,
      departmentsIsLoading
    } = this.props
    // Initialize allCourses and allPrograms variables in state once they finish loading to store since the value will
    // change when changing departments
    if (
      !coursesIsLoading &&
      courses.length > 0 &&
      this.state.allCoursesRetrieved.length === 0
    ) {
      this.setState({ allCoursesRetrieved: courses })
      this.setState({ filteredCourses: courses })
      this.setState({ allCoursesCount: coursesCount })
    }
    if (
      !programsIsLoading &&
      programs.length > 0 &&
      this.state.allProgramsRetrieved.length === 0
    ) {
      this.setState({ allProgramsRetrieved: programs })
      this.setState({ filteredPrograms: programs })
      this.setState({ allProgramsCount: programsCount })
    }
    if (!departmentsIsLoading && departments.length > 0) {
      if (!this.state.filterDepartmentsByTabNameCalled) {
        // initialize the departments on page load.
        this.setState({ filterDepartmentsByTabNameCalled: true }) // This line must be before calling changeSelectedTab for the first time
        // or else componentDidUpdate will end up in an infinite loop.
        this.changeSelectedTab(this.state.tabSelected)
      }
      if (!coursesIsLoading && !this.state.filterCoursesCalled) {
        this.setState({ filterCoursesCalled: true }) // This line must be before calling filteredCoursesOrProgramsByDepartmentSlug
        // or else componentDidUpdate will end up in an infinite loop.
        const filteredCourses = this.filteredCoursesOrProgramsByDepartmentSlug(
          this.state.selectedDepartment,
          this.state.allCoursesRetrieved,
          COURSES_TAB
        )
        this.setState({ filteredCourses: filteredCourses })
      }
    }
    this.io = new window.IntersectionObserver(
      this.bottomOfLoadedCatalogCallback,
      { threshold: 1.0 }
    )
    this.io.observe(this.container.current)
  }

  /**
   * Returns an array of departments objects which have one or more course(s) or program(s)
   * related to them depending on the currently selected tab.
   * @param {string} selectedTabName the name of the currently selected tab.
   */
  filterDepartmentsByTabName(selectedTabName: string) {
    if (!this.props.departmentsIsLoading) {
      const { departments } = this.props
      const allDepartments = { name: ALL_DEPARTMENTS, slug: ALL_DEPARTMENTS }
      if (selectedTabName === COURSES_TAB) {
        return [
          ...new Set([
            allDepartments,
            ...departments.flatMap(department =>
              department.course_ids.length > 0 ? department : []
            )
          ])
        ]
      } else {
        return [
          ...new Set([
            allDepartments,
            ...departments.flatMap(department =>
              department.program_ids.length > 0 ? department : []
            )
          ])
        ]
      }
    }
  }

  /**
   * Resets the query-related variables to their default values
   * in order to ensure paged API requests start at page 1.
   * This is called when a different department or tab is selected.
   */
  resetQueryVariablesToDefault() {
    if (this.state.tabSelected === COURSES_TAB) {
      this.setState({ courseQueryPage: 1 })
      this.setState({ courseQueryIDListString: "" })
    } else {
      // Required in order to support filtering programs by department via url.
      this.setState({ filterProgramsCalled: false })
    }
  }

  /**
   * Updates the following state variables:
   * - tabSelected, set to the parameter name.
   * - filteredDepartments, based on the return from filterDepartmentsByTabName.
   * Calls changeSelectedDepartment.
   * @param {string} selectedTabName The name of the tab that was selected.
   */
  changeSelectedTab = (selectedTabName: string) => {
    this.setState({ tabSelected: selectedTabName })
    const filteredDepartments = this.filterDepartmentsByTabName(selectedTabName)
    this.setState({
      filteredDepartments: filteredDepartments
    })
    const departmentObject = this.getDepartmentObjectFromSlug(
      this.state.selectedDepartment
    )
    // Check if the currently selected department exists for the
    // newly selected tab.
    const departmentExistsForTab = filteredDepartments.find(
      department => department.slug === this.state.selectedDepartment
    )
    if (!departmentExistsForTab || typeof departmentObject === "undefined") {
      // If there are no catalog items on this tab
      // with an associated Department matching the
      // selected department, update the selected department
      // to ALL_DEPARTMENTS.
      this.changeSelectedDepartment(ALL_DEPARTMENTS, selectedTabName)
      if (selectedTabName === PROGRAMS_TAB) {
        this.retrieveMorePrograms()
      }
      if (selectedTabName === COURSES_TAB) {
        this.retrieveMoreCourses()
      }
    } else {
      // Update either the programs or courses based on the currently
      // selected tab.
      this.changeSelectedDepartment(departmentObject.slug, selectedTabName)
      if (selectedTabName === PROGRAMS_TAB) {
        this.retrieveMorePrograms()
      }
      if (selectedTabName === COURSES_TAB) {
        this.retrieveMoreCoursesByDepartment(departmentObject)
      }
    }
  }

  /**
   * Set the value of this.state.mobileFilterWindowExpanded.
   * @param {boolean} expanded The value that this.state.mobileFilterWindowExpanded will be set to.
   */
  toggleMobileFilterWindowExpanded = (expanded: boolean) => {
    this.setState({ mobileFilterWindowExpanded: expanded })
  }

  /**
   * Returns the Department object that has a slug matching the parameter.
   * If no Department has a slug matching the parameter, undefined is returned.
   * Undefined will be returned if the parameter is ALL_DEPARTMENTS.
   *
   * @param {string} selectedDepartmentSlug The department slug.
   *
   * @returns {Department} The department object with a slug value matching the parameter. Otherwise, undefined.
   */
  getDepartmentObjectFromSlug(selectedDepartmentSlug: string) {
    const { departments } = this.props
    if (departments) {
      return departments.find(
        department => department.slug === selectedDepartmentSlug
      )
    }
    return undefined
  }

  /**
   * Changes the selectedDepartment state variable and, depending on the value of tabSelected, updates either
   * the filteredCourses or filteredPrograms state variable.
   * Resets the query variables via resetQueryVariablesToDefault.
   * Closes the mobile view filter window.
   * @param {string} selectedDepartmentSlug The department slug to set selectedDepartment to and filter courses by.
   * @param {string} tabSelected The currently selected tab.  Optional.  If not defined, this.state.tabSelected is used
   * when updating this.props.history.
   */
  changeSelectedDepartment = (
    selectedDepartmentSlug: string,
    tabSelected: string
  ) => {
    this.resetQueryVariablesToDefault()
    this.toggleMobileFilterWindowExpanded(false)
    let tabSelectedValue = tabSelected
    if (typeof tabSelectedValue === "undefined") {
      tabSelectedValue = this.state.tabSelected
    }

    let departmentObjectForTab = undefined
    if (
      selectedDepartmentSlug !== ALL_DEPARTMENTS &&
      selectedDepartmentSlug !== ""
    ) {
      departmentObjectForTab = this.getDepartmentObjectFromSlug(
        selectedDepartmentSlug
      )
    }
    if (typeof departmentObjectForTab === "undefined") {
      // If departmentObjectForTab is undefined, then the selectedDepartmentSlug
      // does not exist or ALL_DEPARTMENTS has been selected.
      this.setState({ selectedDepartment: ALL_DEPARTMENTS })
      this.props.history.push(
        this.getUpdatedURL(tabSelectedValue, ALL_DEPARTMENTS)
      )
      // Return either all of the courses or programs
      // depending on the current tabSelected value.
      if (tabSelectedValue === COURSES_TAB) {
        this.setState({ filteredCourses: this.state.allCoursesRetrieved })
      } else {
        this.setState({ filteredPrograms: this.state.allProgramsRetrieved })
      }
    } else {
      // A valid department or ALL_DEPARTMENTS has been selected.
      this.setState({ selectedDepartment: selectedDepartmentSlug })
      this.props.history.push(
        this.getUpdatedURL(tabSelectedValue, selectedDepartmentSlug)
      )
      // We need to attempt to retrieve more courses or programs
      // in order to populate the filtered catalog page.
      if (tabSelectedValue === COURSES_TAB) {
        this.retrieveMoreCoursesByDepartment(departmentObjectForTab)
      } else if (tabSelectedValue === PROGRAMS_TAB) {
        this.retrieveMorePrograms(selectedDepartmentSlug)
      }
    }
  }

  /**
   * Retrieves more courses via API request.
   * If the courseQueryIDListString parameter is specified
   * then the API request will only pertain to the those.
   * If the courseQueryIDListString parameter is NOT specified,
   * then a paginated API request will be made using the
   * courseQueryPage state variable as the page number.
   *
   * The following state variables are updated:
   * - courseQueryPage, increment by 1 only when we are NOT making an API request for specific course IDs.
   * - allCoursesRetrieved, updated with the courses in the API response.
   * - filteredCourses, updated with the courses in the API response.
   * - filterCoursesCalled, set to true.
   *
   * @param {string} courseQueryIDListString a string containing a list of course IDs.  This is optional.  When not defined,
   * this method will make paginated API requests without specifying course IDs.
   */
  retrieveMoreCourses(courseQueryIDListString: string) {
    const { coursesIsLoading, getNextCoursePage } = this.props

    // If courseQueryIDListString is defined when calling this method,
    // then we will only request the first page of API results since
    // the API request will contain the course IDs we're interested in.
    let courseQueryPage = 1

    // If courseQueryIDListString was not defined when calling this method, then we
    // should request paginated API results using courseQueryPage for the page number.
    if (typeof courseQueryIDListString === "undefined") {
      courseQueryIDListString = this.state.courseQueryIDListString
      courseQueryPage = this.state.courseQueryPage
    }
    if (!this.state.isLoadingMoreItems && !coursesIsLoading) {
      this.setState({ isLoadingMoreItems: true })
      getNextCoursePage(
        courseQueryPage,
        courseQueryIDListString.toString()
      ).then(response => {
        this.setState({ courseQueryPage: courseQueryPage + 1 })
        if (response.body.results) {
          const allCourses = this.mergeCourseOrProgramArrays(
            this.state.allCoursesRetrieved,
            response.body.results
          )
          this.setState({
            allCoursesRetrieved: allCourses
          })
          const filteredCourses = this.filteredCoursesOrProgramsByDepartmentSlug(
            this.state.selectedDepartment,
            allCourses,
            COURSES_TAB
          )
          this.setState({ filteredCourses: filteredCourses })
          this.setState({ filterCoursesCalled: true })
        }
        this.setState({ isLoadingMoreItems: false })
      })
    }
  }

  /**
   * Retrieves courses, that are associated with the department parameter.
   * This will only retrieve courses which have not already
   * been retrieved.  If all courses associated with the department have
   * already been retrieved, this will only update the following state variables:
   * - filteredCourses.
   * - filterCoursesCalled.
   *
   * @param {Department} selectedDepartmentObject The department object containing associated course IDs.
   */
  retrieveMoreCoursesByDepartment(selectedDepartmentObject: Department) {
    // Only request more courses if we have not already retrieved all courses associated with the department.
    const remainingIDs = selectedDepartmentObject.course_ids.filter(
      id =>
        !this.state.allCoursesRetrieved.map(course => course.id).includes(id)
    )
    if (remainingIDs.length > 0) {
      this.retrieveMoreCourses(remainingIDs)
    } else {
      // If we have already retrieved all courses associated with the department,
      // just update the filteredCourses state variable.
      const filteredCourses = this.filteredCoursesOrProgramsByDepartmentSlug(
        selectedDepartmentObject.slug,
        this.state.allCoursesRetrieved,
        COURSES_TAB
      )
      this.setState({ filteredCourses: filteredCourses })
      this.setState({ filterCoursesCalled: true })
    }
  }

  /**
   * Retrieves another page of Programs via API request when:
   * - There is a next page of prorgams available (programsNextPage).
   * - isLoadingMoreItems is false.
   * - programsIsLoading is false.
   * - All of the programs have not already been retrieved.
   * This will update the following state variables:
   * - allProgramsRetrieved, updated by adding newly retrieved programs.
   * - programQueryPage, increment by 1.
   * - filterProgramsCalled set to true.
   *
   * @param {string} selectedDepartmentSlug The department slug for the currently selected department.  This parameter is optional.
   * If this is not defined when calling the method, the value of this.state.selectedDepartment will be used.
   */
  retrieveMorePrograms(selectedDepartmentSlug: string) {
    const {
      programsIsLoading,
      programsNextPage,
      getNextProgramPage
    } = this.props
    let currentDepartmentSlug = this.state.selectedDepartment
    if (typeof selectedDepartmentSlug !== "undefined") {
      currentDepartmentSlug = selectedDepartmentSlug
    }
    if (
      !programsIsLoading &&
      programsNextPage &&
      !this.state.isLoadingMoreItems &&
      this.state.allProgramsRetrieved.length < this.state.allProgramsCount
    ) {
      this.setState({ isLoadingMoreItems: true })
      getNextProgramPage(this.state.programQueryPage).then(response => {
        const updatedAllPrograms = this.mergeCourseOrProgramArrays(
          this.state.allProgramsRetrieved,
          response.body.results
        )
        this.setState({ allProgramsRetrieved: updatedAllPrograms })
        this.setState({ programQueryPage: this.state.programQueryPage + 1 })
        this.setState({ isLoadingMoreItems: false })
        const filteredPrograms = this.filteredCoursesOrProgramsByDepartmentSlug(
          currentDepartmentSlug,
          updatedAllPrograms,
          PROGRAMS_TAB
        )
        this.setState({ filteredPrograms: filteredPrograms })
      })
    } else {
      // All programs have been retrieved from the API.  We just need to update the
      // filteredPrograms state variable.
      const filteredPrograms = this.filteredCoursesOrProgramsByDepartmentSlug(
        currentDepartmentSlug,
        this.state.allProgramsRetrieved,
        PROGRAMS_TAB
      )
      this.setState({ filteredPrograms: filteredPrograms })
    }
    this.setState({ filterProgramsCalled: true })
  }

  /**
   * Returns the union of two arrays of type CourseDetailWithRuns or Programs based on the
   * ID of each object in the array.
   * @param {Array<CourseDetailWithRuns | Program>} catalogItems
   * @returns {Array<CourseDetailWithRuns | Program>} Union of both array parameters.
   */
  mergeCourseOrProgramArrays(
    aArray: Array<CourseDetailWithRuns | Program>,
    bArray: Array<CourseDetailWithRuns | Program>
  ) {
    const aIds = aArray.map(a => a.id)
    const uniqueObjects = bArray.filter(b => !aIds.includes(b.id))
    return aArray.concat(uniqueObjects)
  }

  /**
   * Returns a filtered array of catalog items that are associated with a
   * Department whose name variable matches the selectedDepartment argument.
   * The association between catalogItems and Departments is determined by the
   * value of the tabSelected state variable:
   * - If tabSelected equals COURSES_TAB, then the Department's course_ids array is compared
   * with the catalog items IDs for matching IDs.
   * - If tabSelected does not equal COURSES_TAB, then the Department's program_ids array is compared
   * with the catalog items IDs for matching IDs.
   * If selectedDepartment equals ALL_DEPARTMENTS, then the catalogItems array is returned.
   * @param {Array<CourseDetailWithRuns | Program>} catalogItems An array of catalog items which will be filtered based on their associated Departments.
   * @param {string} selectedDepartmentSlug The Department slug which is used to compare with items in the catalogItems array.
   * @param {string} tabSelected The tab currently selected.  This is used to indicate whether the catalogItems parameter contains programs or courses.
   */
  filteredCoursesOrProgramsByDepartmentSlug(
    selectedDepartmentSlug: string,
    catalogItems: Array<CourseDetailWithRuns | Programs>,
    tabSelected: string
  ) {
    const selectedDepartmentObject = this.getDepartmentObjectFromSlug(
      selectedDepartmentSlug
    )
    if (
      selectedDepartmentSlug === ALL_DEPARTMENTS ||
      typeof selectedDepartmentObject === "undefined"
    ) {
      this.setState({ selectedDepartment: ALL_DEPARTMENTS })
      return catalogItems
    } else {
      if (tabSelected === COURSES_TAB) {
        return catalogItems.filter(catalogItem =>
          selectedDepartmentObject.course_ids.includes(catalogItem.id)
        )
      } else {
        return catalogItems.filter(catalogItem =>
          selectedDepartmentObject.program_ids.includes(catalogItem.id)
        )
      }
    }
  }

  /**
   * Returns the updated URL based on the given state of the catalog page.
   * @returns {string}
   */
  getUpdatedURL(tabSelected, selectedDepartment) {
    if (selectedDepartment === ALL_DEPARTMENTS) {
      return `/catalog/${tabSelected}`
    }
    return `/catalog/${tabSelected}/${selectedDepartment}`
  }

  /**
   * Returns the number of catalog items based on the selectedDepartment
   * and the selectedTabName state variables.
   * If the selectedDepartment is "All Departments" and selectedTabName is equal to COURSES_TAB,
   * then total number of courses is returned.
   * If the selectedDepartment is "All Departments" and selectedTabName is equal not equal to
   * COURSES_TAB, then total number of programs is returned.
   * If the selectDepartment state variable is equal to "slug" value for one of the entries in the
   * "departments" prop, then the "course_ids" or "program_ids" value for that department, depending on the value
   * of selectedTabName, will be displayed.
   * If the selectedDepartment is not found in the departments array, 0 is returned.
   * @returns {number} the number of courses or programs associated with the department matching
   * the selectedDepartment state variable.
   */
  renderNumberOfCatalogItems() {
    const { departments } = this.props
    if (this.state.selectedDepartment === ALL_DEPARTMENTS) {
      return this.state.tabSelected === COURSES_TAB
        ? this.state.allCoursesCount
        : this.state.allProgramsCount
    } else if (!departments) return 0
    const departmentSlugs = this.state.filteredDepartments.map(
      department => department.slug
    )
    if (!departmentSlugs.includes(this.state.selectedDepartment)) {
      return 0
    } else {
      if (this.state.tabSelected === COURSES_TAB) {
        return this.state.filteredDepartments.find(
          department => department.slug === this.state.selectedDepartment
        ).course_ids.length
      } else {
        return this.state.filteredDepartments.find(
          department => department.slug === this.state.selectedDepartment
        ).program_ids.length
      }
    }
  }

  /**
   * Returns the html for the catalog count based on the selected tab, either Courses or Programs.
   * This return is singular or plural based on the count.
   * @returns {Element}
   */
  renderCatalogCount() {
    const count = this.renderNumberOfCatalogItems()
    const tab = this.state.tabSelected
    return (
      <h2 className="catalog-count">
        {/* Hidden on small screens. */}
        {count} {count > 1 ? tab : tab.slice(0, -1)}
      </h2>
    )
  }

  /**
   * Renders a single course catalog card.
   * @param {CourseDetailWithRuns} course The course instance used to populate the card.
   */
  renderCourseCatalogCard(course: CourseDetailWithRuns) {
    return (
      <li key={`course-card-${course.id}`}>
        <a href={course.page.page_url} key={course.id}>
          <div className="col catalog-item">
            <img
              src={course?.page?.feature_image_src}
              key={course.id + course?.page?.feature_image_src}
              alt=""
            />
            <div className="catalog-item-description">
              <div className="start-date-description">
                {getStartDateText(course)}
              </div>
              <div className="item-title">{course.title}</div>
            </div>
          </div>
        </a>
      </li>
    )
  }

  /**
   * Renders a single program catalog card.
   * @param {Program} program The program instance used to populate the card.
   */
  renderProgramCatalogCard(program: Program) {
    return (
      <li key={`program-card-${program.id}`}>
        <a href={program.page.page_url} key={program.id}>
          <div className="col catalog-item">
            <div className="program-image-and-badge">
              <img
                src={program?.page?.feature_image_src}
                key={program.id + program?.page?.feature_image_src}
                alt=""
              />
              <div className="program-type-badge">{program.program_type}</div>
            </div>
            <div className="catalog-item-description">
              <div className="item-title">{program.title}</div>
            </div>
          </div>
        </a>
      </li>
    )
  }

  /**
   * Dynamically renders rows of cards in the catalog.  Each row can contain up to {ITEMS_PER_ROW} course or program cards.
   * @param {Array<CourseDetailWithRuns | Program>} itemsInCatalog The items associated with the currently selected catalog page.
   * @param {Function} renderCatalogCardFunction The card render function that will be used for each item on the current catalog page.
   */
  renderCatalogRows(
    itemsInCatalog: Array<CourseDetailWithRuns | Program>,
    renderCatalogCardFunction: Function
  ) {
    return (
      <ul id="catalog-grid">
        {itemsInCatalog.map(x => renderCatalogCardFunction(x))}
      </ul>
    )
  }

  /**
   * Renders the entire catalog of course or program cards based on the catalog tab selected.
   */
  renderCatalog() {
    const { filteredCourses, filteredPrograms, tabSelected } = this.state

    if (
      filteredCourses.length === 0 &&
      (this.props.coursesIsLoading || this.props.programsIsLoading)
    ) {
      return courseLoaderGrid
    }
    if (tabSelected === COURSES_TAB && filteredCourses.length > 0) {
      return this.renderCatalogRows(
        filteredCourses,
        this.renderCourseCatalogCard.bind(this)
      )
    } else if (tabSelected === PROGRAMS_TAB) {
      return this.renderCatalogRows(
        filteredPrograms,
        this.renderProgramCatalogCard.bind(this)
      )
    }
  }

  /**
   * Returns the rendering of the Department sidebar.
   */
  renderDepartmentSideBarList() {
    const departmentSideBarListItems = []
    this.state.filteredDepartments.forEach(department =>
      departmentSideBarListItems.push(
        <li
          className={`sidebar-link ${
            this.state.selectedDepartment === department.slug
              ? "department-selected-link"
              : "department-link"
          }`}
          key={this.state.tabSelected + department.slug}
        >
          <button
            onClick={() =>
              this.changeSelectedDepartment(
                department.slug,
                this.state.tabSelected
              )
            }
          >
            {department.name}
          </button>
        </li>
      )
    )
    return (
      <nav
        className="sticky-top"
        id="department-sidebar"
        aria-label="department filters"
      >
        <ul id="department-sidebar-link-list">{departmentSideBarListItems}</ul>
      </nav>
    )
  }

  render() {
    return (
      <div>
        <div id="catalog-page">
          <div id="catalog-title">
            {/* Hidden on small screens. */}
            <h1 className="d-none d-md-block">MITx Online Catalog</h1>
            {/* Visible on small screens. */}
            <div className="d-block d-md-none" id="mobile-catalog-title">
              <button
                onClick={() =>
                  this.toggleMobileFilterWindowExpanded(
                    !this.state.mobileFilterWindowExpanded
                  )
                }
              />
              <h1>
                Catalog
                <small>
                  {this.state.selectedDepartment === ALL_DEPARTMENTS
                    ? ""
                    : this.state.selectedDepartment}
                </small>
              </h1>
            </div>
          </div>
          <div className="container">
            <div id="course-catalog-navigation">
              {/* Only visible on small screen when mobileFilterWindowExpanded is true. */}
              <div
                className={`mobile-filter-overlay ${
                  this.state.mobileFilterWindowExpanded
                    ? "slide-mobile-filter-overlay"
                    : "hidden-mobile-filter-overlay"
                }`}
              >
                {this.renderDepartmentSideBarList()}
              </div>
              <div className="container-fluid">
                <div className="row" id="tab-row">
                  <div className="col catalog-animation d-sm-flex d-md-inline-flex">
                    <TransitionGroup id="tab-animation-grid">
                      <CSSTransition
                        key={this.state.tabSelected}
                        timeout={300}
                        classNames="messageout"
                      >
                        <div className="row" id="tabs">
                          <div
                            className={`col ${
                              this.state.tabSelected === COURSES_TAB
                                ? "selected-tab"
                                : "unselected-tab"
                            }`}
                          >
                            <button
                              onClick={() =>
                                this.changeSelectedTab(COURSES_TAB)
                              }
                              tabIndex="0"
                            >
                              Courses{" "}
                              <div className="product-number d-inline-block d-sm-none">
                                ({this.renderNumberOfCatalogItems()})
                              </div>
                            </button>
                          </div>
                          <div
                            className={`col ${
                              this.state.tabSelected === PROGRAMS_TAB
                                ? "selected-tab"
                                : "unselected-tab"
                            } ${
                              this.props.programsCount ? "" : "display-none"
                            }`}
                          >
                            <button
                              onClick={() =>
                                this.changeSelectedTab(PROGRAMS_TAB)
                              }
                            >
                              Programs{" "}
                              <div className="product-number d-inline-block d-sm-none">
                                ({this.renderNumberOfCatalogItems()})
                              </div>
                            </button>
                          </div>
                        </div>
                      </CSSTransition>
                    </TransitionGroup>
                  </div>
                  <div className="col catalog-page-item-count d-none d-sm-block">
                    <div
                      className="catalog-count-animation"
                      role="status"
                      aria-atomic="true"
                    >
                      <TransitionGroup id="count-animation-grid">
                        <CSSTransition
                          key={this.state.tabSelected}
                          timeout={300}
                          classNames="count"
                        >
                          {this.renderCatalogCount()}
                        </CSSTransition>
                      </TransitionGroup>
                    </div>
                  </div>
                </div>
                <div className="catalog-animation">
                  <TransitionGroup>
                    <CSSTransition
                      key={this.state.tabSelected}
                      timeout={300}
                      classNames="messageout"
                    >
                      <div>{this.renderCatalog()}</div>
                    </CSSTransition>
                  </TransitionGroup>
                </div>
                {this.state.isLoadingMoreItems ? courseLoaderGrid : null}
                {/* span is used to detect when the learner has scrolled to the bottom of the catalog page. */}
                <span ref={this.container}></span>
              </div>
            </div>
          </div>
        </div>
      </div>
    )
  }
}
const courseLoaderGrid = (
  <div id="catalog-grid">
    <CourseLoader />
    <CourseLoader />
    <CourseLoader />
  </div>
)

const getNextCoursePage = (page, ids) =>
  requestAsync({
    ...coursesQuery(page, ids),
    force: true
  })

const getNextProgramPage = page =>
  requestAsync({
    ...programsQuery(page),
    force: true
  })

const mapPropsToConfig = () => [
  coursesQuery(1, ""),
  programsQuery(1),
  departmentsQuery(1)
]

const mapDispatchToProps = {
  getNextCoursePage:  getNextCoursePage,
  getNextProgramPage: getNextProgramPage
}

const mapStateToProps = createStructuredSelector({
  courses:              coursesSelector,
  coursesCount:         coursesCountSelector,
  coursesNextPage:      coursesNextPageSelector,
  programs:             programsSelector,
  programsCount:        programsCountSelector,
  programsNextPage:     programsNextPageSelector,
  departments:          departmentsSelector,
  coursesIsLoading:     pathOr(true, ["queries", coursesQueryKey, "isPending"]),
  programsIsLoading:    pathOr(true, ["queries", programsQueryKey, "isPending"]),
  departmentsIsLoading: pathOr(true, [
    "queries",
    departmentsQueryKey,
    "isPending"
  ])
})

export default compose(
  connect(mapStateToProps, mapDispatchToProps),
  connectRequest(mapPropsToConfig)
)(CatalogPage)
