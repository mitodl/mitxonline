import React, { useEffect, useState } from "react"
import { CSSTransition, TransitionGroup } from "react-transition-group"
import moment from "moment"
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
  departments: ?Array<Department>
}

// Department filter name for all items.
const ALL_DEPARTMENTS = "All Departments"

// Program tab name.
const PROGRAMS_TAB = "programs"

// Course tab name.
const COURSES_TAB = "courses"

function CatalogPage(props) {
  const [tabSelected, setTabSelected] = useState(COURSES_TAB)
  const [allCoursesRetrieved, setAllCoursesRetrieved] = useState([])
  const [allProgramsRetrieved, setAllProgramsRetrieved] = useState([])
  const [filteredCourses, setFilteredCourses] = useState([])
  const [filteredPrograms, setFilteredPrograms] = useState([])
  const [filterProgramsCalled, setFilterProgramsCalled] = useState(false)
  const [filterCoursesCalled, setFilterCoursesCalled] = useState(false)
  const [filteredDepartments, setFilteredDepartments] = useState([])
  const [filterDepartmentsCalled, setFilterDepartmentsCalled] = useState(false)
  const [selectedDepartment, setSelectedDepartment] = useState(ALL_DEPARTMENTS)
  const [mobileFilterWindowExpanded, setMobileFilterWindowExpanded] = useState(
    false
  )
  const [courseQueryPage, setCourseQueryPage] = useState(1)
  const [programQueryPage, setProgramQueryPage] = useState(1)
  const [isLoadingMoreItems, setIsLoadingMoreItems] = useState(false)

  const courseLoaderGrid = (
    <div id="catalog-grid">
      <CourseLoader />
      <CourseLoader />
      <CourseLoader />
    </div>
  )
  let io = null
  let container
  container = React.createRef(null)

  useEffect(() => {
    if (io) {
      return () => {
        io.disconnect()
      }
    } else {
      return () => {
        console.log("Nothing to disconnect")
      }
    }
  }, [])

  /**
   * Makes another API call to the courses or programs endpoint if there is
   * a next page defined in the prior request.
   * Appends the courses or programs from the API call to the current allCoursesRetrieved
   * or allProgramsRetrieved state variable.  Increments the courseQueryPage or programQueryPage
   * state variable.  Updates the filteredCourses or filteredPrograms state variable using the
   * updated allCoursesRetrieved or allProgramsRetrieved state variable.
   */
  const bottomOfLoadedCatalogCallback = async entries => {
    const [entry] = entries
    if (entry.isIntersecting) {
      if (tabSelected === COURSES_TAB) {
        // Only request the next page if a next page exists (coursesNextPage)
        // and if we aren't already requesting the next page (isLoadingMoreItems).
        if (props.coursesNextPage && !isLoadingMoreItems) {
          setIsLoadingMoreItems(true)
          setCourseQueryPage(courseQueryPage + 1)
          const response = await props.getNextCoursePage(courseQueryPage)
          setIsLoadingMoreItems(false)
          if (response.body.results) {
            const filteredCoursesByDepartment = filteredCoursesBasedOnCourseRunCriteria(
              selectedDepartment,
              [...allCoursesRetrieved, ...response.body.results]
            )
            setFilteredCourses(filteredCoursesByDepartment)
            setAllCoursesRetrieved([
              ...allCoursesRetrieved,
              ...response.body.results
            ])
          }
        }
      } else {
        if (props.programsNextPage) {
          setIsLoadingMoreItems(true)
          const response = await props.getNextProgramPage(programQueryPage + 1)
          setIsLoadingMoreItems(false)
          setProgramQueryPage(programQueryPage + 1)
          if (response.body.results) {
            const filteredProgramsByDepartment = filteredProgramsByDepartmentAndCriteria(
              selectedDepartment,
              [...allProgramsRetrieved, ...response.body.results]
            )
            setFilteredPrograms(filteredProgramsByDepartment)
            setAllProgramsRetrieved([
              ...allProgramsRetrieved,
              ...response.body.results
            ])
          }
        }
      }
    }
  }
  /**
   * Updates the filteredCourses state variable
   * once coursesIsLoading is false..  Adds an observer to detect when
   * the learner has scrolled to the bottom of the visible catalog items.
   * Updates the filteredDepartments state variable once departmentsIsLoading
   * is false.
   */
  useEffect(() => {
    if (!props.coursesIsLoading && !filterCoursesCalled) {
      setFilterCoursesCalled(true)
      setAllCoursesRetrieved(props.courses)

      const filteredCoursesByDepartment = filteredCoursesBasedOnCourseRunCriteria(
        selectedDepartment,
        props.courses
      )
      setFilteredCourses(filteredCoursesByDepartment)

      // Detect when the bottom of the catalog page has been reached and display more catalog items.
      io = new window.IntersectionObserver(bottomOfLoadedCatalogCallback, {
        threshold: 1.0
      })
      io.observe(container.current)
    }

    if (!props.departmentsIsLoading && !filterDepartmentsCalled) {
      setFilterDepartmentsCalled(true)
      setFilteredDepartments(filterDepartmentsByTabName(tabSelected))
    }
    if (!props.programsIsLoading && !filterProgramsCalled) {
      setFilterProgramsCalled(true)
      setAllProgramsRetrieved(props.programs)
      const filteredProgramsByDepartment = filteredProgramsByDepartmentAndCriteria(
        selectedDepartment,
        props.programs
      )
      setFilteredPrograms(filteredProgramsByDepartment)
    }
  })

  /**
   * Updates selectedDepartment to {ALL_DEPARTMENTS},
   * updates tabSelected to the parameter,
   * updates filteredDepartments
   * names from the catalog items in the selected tab,
   * updates filteredPrograms to equal the programs
   * which meet the criteria to be displayed in the catalog.
   * @param {string} selectTabName The name of the tab that was selected.
   */
  const changeSelectedTab = (selectTabName: string) => {
    setTabSelected(selectTabName)

    if (selectTabName === PROGRAMS_TAB) {
      if (!props.programsIsLoading) {
        const programsToFilter = []
        // The first time that a user switches to the programs tab, allProgramsRetrieved will be
        // empty and should be populated with the results from the first programs API call.
        if (allProgramsRetrieved.length === 0) {
          setAllProgramsRetrieved(props.programs)
          programsToFilter.push(...props.programs)
        } else {
          programsToFilter.push(...allProgramsRetrieved)
        }

        const filteredPrograms = filteredProgramsByDepartmentAndCriteria(
          selectedDepartment,
          programsToFilter
        )
        setFilteredPrograms(filteredPrograms)
      }
    }
    setFilteredDepartments(filterDepartmentsByTabName(selectTabName))
  }

  /**
   * Returns an array of departments names which have one or more course(s) or program(s)
   * related to them depending on the currently selected tab.
   * @param {string} selectedTabName the name of the currently selected tab.
   */
  const filterDepartmentsByTabName = (selectedTabName: string) => {
    if (!props.departmentsIsLoading) {
      if (selectedTabName === COURSES_TAB) {
        return [
          ...new Set([
            ALL_DEPARTMENTS,
            ...props.departments.flatMap(department =>
              department.courses > 0 ? department.name : []
            )
          ])
        ]
      } else {
        return [
          ...new Set([
            ALL_DEPARTMENTS,
            ...props.departments.flatMap(department =>
              department.programs > 0 ? department.name : []
            )
          ])
        ]
      }
    }
  }

  /**
   * Set the value of mobileFilterWindowExpanded.
   * @param {boolean} expanded The value that mobileFilterWindowExpanded will be set to.
   */
  const toggleMobileFilterWindowExpanded = (expanded: boolean) => {
    setMobileFilterWindowExpanded(expanded)
  }

  /**
   * Changes the selectedDepartment state variable and, depending on the value of tabSelected, updates either
   * the filteredCourses or filteredPrograms state variable.
   * @param {string} selectedDepartment The department name to set selectedDepartment to and filter courses by.
   */
  const changeSelectedDepartment = (selectedDepartment: string) => {
    setSelectedDepartment(selectedDepartment)
    setFilteredCourses(
      filteredCoursesBasedOnCourseRunCriteria(
        selectedDepartment,
        allCoursesRetrieved
      )
    )
    setFilteredPrograms(
      filteredProgramsByDepartmentAndCriteria(
        selectedDepartment,
        allProgramsRetrieved
      )
    )
    toggleMobileFilterWindowExpanded(false)
  }

  /**
   * Returns a filtered array of Course Runs which are live, define a start date,
   * enrollment start date is before the current date and time, and
   * enrollment end date is not defined or is after the current date and time.
   * @param {Array<BaseCourseRun>} courseRuns The array of Course Runs apply the filter to.
   */
  const validateCoursesCourseRuns = (courseRuns: Array<BaseCourseRun>) => {
    return courseRuns.filter(
      courseRun =>
        courseRun.live &&
        courseRun.start_date &&
        moment(courseRun?.enrollment_start).isBefore(moment()) &&
        (!courseRun.enrollment_end ||
          moment(courseRun.enrollment_end).isAfter(moment()))
    )
  }

  /**
   * Returns a filtered array of courses which have: an associated Department name matching the selectedDepartment
   * if the selectedDepartment does not equal "All Departments",
   * an associated page which is live, and at least 1 associated Course Run.
   * @param {Array<CourseDetailWithRuns>} courses An array of courses which will be filtered by Department.
   * @param {string} selectedDepartment The Department name used to compare against the courses in the array.
   */
  const filteredCoursesBasedOnCourseRunCriteria = (
    selectedDepartment: string,
    courses: Array<CourseDetailWithRuns>
  ) => {
    return courses.filter(
      course =>
        (selectedDepartment === ALL_DEPARTMENTS ||
          course.departments
            .map(department => department.name)
            .includes(selectedDepartment)) &&
        course?.page?.live &&
        course.courseruns.length > 0 &&
        validateCoursesCourseRuns(course.courseruns).length > 0
    )
  }

  /**
   * Returns an array of Programs which have page.live = true and a department name which
   * matches the currently selected department.
   * @param {Array<Program>} programs An array of Programs which will be filtered by Department and other criteria.
   * @param {string} selectedDepartment The Department name used to compare against the courses in the array.
   */
  const filteredProgramsByDepartmentAndCriteria = (
    selectedDepartment: string,
    programs: Array<Program>
  ) => {
    return programs.filter(
      program =>
        selectedDepartment === ALL_DEPARTMENTS ||
        program.departments
          .map(department => department)
          .includes(selectedDepartment)
    )
  }

  /**
   * Returns the number of courseRuns or programs based on the selected catalog tab.
   */
  const renderNumberOfCatalogItems = () => {
    if (
      tabSelected === PROGRAMS_TAB &&
      selectedDepartment === ALL_DEPARTMENTS
    ) {
      return props.programsCount
    } else if (
      tabSelected === PROGRAMS_TAB &&
      selectedDepartment !== ALL_DEPARTMENTS
    ) {
      return props.departments.find(
        department => department.name === selectedDepartment
      ).programs
    }
    if (tabSelected === COURSES_TAB && selectedDepartment === ALL_DEPARTMENTS) {
      return props.coursesCount
    } else if (
      tabSelected === COURSES_TAB &&
      selectedDepartment !== ALL_DEPARTMENTS
    ) {
      return props.departments.find(
        department => department.name === selectedDepartment
      ).courses
    }
  }

  /**
   * Renders a single course catalog card.
   * @param {CourseDetailWithRuns} course The course instance used to populate the card.
   */
  const renderCourseCatalogCard = (course: CourseDetailWithRuns) => {
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
  const renderProgramCatalogCard = (program: Program) => {
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
  const renderCatalogRows = (
    itemsInCatalog: Array<CourseDetailWithRuns | Program>,
    renderCatalogCardFunction: Function
  ) => {
    return (
      <ul id="catalog-grid">
        {itemsInCatalog.map(x => renderCatalogCardFunction(x))}
      </ul>
    )
  }

  /**
   * Renders the entire catalog of course or program cards based on the catalog tab selected.
   */
  const renderCatalog = () => {
    if (
      filteredCourses.length === 0 &&
      (props.coursesIsLoading || props.programsIsLoading)
    ) {
      return courseLoaderGrid
    }
    if (tabSelected === COURSES_TAB && filteredCourses.length > 0) {
      return renderCatalogRows(filteredCourses, renderCourseCatalogCard)
    } else if (tabSelected === PROGRAMS_TAB) {
      return renderCatalogRows(filteredPrograms, renderProgramCatalogCard)
    }
  }

  /**
   * Returns the rendering of the Department sidebar.
   */
  const renderDepartmentSideBarList = () => {
    const departmentSideBarListItems = []
    filteredDepartments.forEach(department =>
      departmentSideBarListItems.push(
        <li
          className={`sidebar-link ${
            selectedDepartment === department
              ? "department-selected-link"
              : "department-link"
          }`}
          key={tabSelected + department}
        >
          <button
            onClick={() => changeSelectedDepartment(department, tabSelected)}
          >
            {department}
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
                toggleMobileFilterWindowExpanded(!mobileFilterWindowExpanded)
              }
            />
            <h1>
              Catalog
              <small>
                {selectedDepartment === ALL_DEPARTMENTS
                  ? ""
                  : selectedDepartment}
              </small>
            </h1>
          </div>
        </div>
        <div className="container">
          <div id="course-catalog-navigation">
            {/* Only visible on small screen when mobileFilterWindowExpanded is true. */}
            <div
              className={`mobile-filter-overlay ${
                mobileFilterWindowExpanded
                  ? "slide-mobile-filter-overlay"
                  : "hidden-mobile-filter-overlay"
              }`}
            >
              {renderDepartmentSideBarList()}
            </div>
            <div className="container-fluid">
              <div className="row" id="tab-row">
                <div className="col catalog-animation d-sm-flex d-md-inline-flex">
                  <TransitionGroup id="tab-animation-grid">
                    <CSSTransition
                      key={tabSelected}
                      timeout={300}
                      classNames="messageout"
                    >
                      <div className="row" id="tabs">
                        <div
                          className={`col ${
                            tabSelected === COURSES_TAB
                              ? "selected-tab"
                              : "unselected-tab"
                          }`}
                        >
                          <button
                            onClick={() => changeSelectedTab(COURSES_TAB)}
                            tabIndex="0"
                          >
                            Courses{" "}
                            <div className="product-number d-inline-block d-sm-none">
                              ({filteredCourses.length})
                            </div>
                          </button>
                        </div>
                        <div
                          className={`col ${
                            tabSelected === PROGRAMS_TAB
                              ? "selected-tab"
                              : "unselected-tab"
                          } ${filteredPrograms.length ? "" : "display-none"}`}
                        >
                          <button
                            onClick={() => changeSelectedTab(PROGRAMS_TAB)}
                          >
                            Programs{" "}
                            <div className="product-number d-inline-block d-sm-none">
                              ({filteredPrograms.length})
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
                        key={tabSelected}
                        timeout={300}
                        classNames="count"
                      >
                        <h2>
                          {/* Hidden on small screens. */}
                          {/* Could add logic to display only "course" if only 1 course is showing. */}
                          {renderNumberOfCatalogItems()} {tabSelected}
                        </h2>
                      </CSSTransition>
                    </TransitionGroup>
                  </div>
                </div>
              </div>
              <div className="catalog-animation">
                <TransitionGroup>
                  <CSSTransition
                    key={tabSelected}
                    timeout={300}
                    classNames="messageout"
                  >
                    <div>{renderCatalog()}</div>
                  </CSSTransition>
                </TransitionGroup>
              </div>
              {isLoadingMoreItems ? courseLoaderGrid : null}
              {/* span is used to detect when the learner has scrolled to the bottom of the catalog page. */}
              <span ref={container}></span>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

const mapPropsToConfig = () => [
  coursesQuery(1),
  programsQuery(1),
  departmentsQuery(1)
]

const mapDispatchToProps = {
  getNextCoursePage:  props.getNextCoursePage,
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
