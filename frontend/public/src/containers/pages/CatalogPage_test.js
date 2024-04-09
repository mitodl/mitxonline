// @flow
/* global SETTINGS: false */
import { expect } from "chai"
import moment from "moment-timezone"
import IntegrationTestHelper from "../../util/integration_test_helper"
import CatalogPage, { CatalogPage as InnerCatalogPage } from "./CatalogPage"
import sinon from "sinon"

const displayedCourse = {
  id:          2,
  title:       "E2E Test Course",
  readable_id: "course-v1:edX+E2E-101",
  courseruns:  [
    {
      title:            "E2E Test Course",
      start_date:       moment(),
      end_date:         moment().add(2, "M"),
      enrollment_start: moment(),
      enrollment_end:   null,
      expiration_date:  null,
      courseware_url:
        "http://edx.odl.local:18000/courses/course-v1:edX+E2E-101+course/",
      courseware_id:    "course-v1:edX+E2E-101+course",
      upgrade_deadline: null,
      is_upgradable:    true,
      is_self_paced:    false,
      run_tag:          "course",
      id:               2,
      live:             true,
      products:         [
        {
          id:                     1,
          price:                  "999.00",
          description:            "course-v1:edX+E2E-101+course",
          is_active:              true,
          product_flexible_price: {
            amount:          null,
            automatic:       false,
            discount_type:   null,
            redemption_type: null,
            max_redemptions: null,
            discount_code:   "",
            payment_type:    null,
            activation_date: null,
            expiration_date: null
          }
        }
      ],
      page: {
        feature_image_src:             "/static/images/mit-dome.png",
        page_url:                      "/courses/course-v1:edX+E2E-101/",
        financial_assistance_form_url: "",
        description:                   "E2E Test Course",
        current_price:                 999.0,
        instructors:                   [],
        live:                          true
      },
      approved_flexible_price_exists: false
    }
  ],
  next_run_id: 2,
  departments: [
    {
      name: "Science"
    }
  ],
  page: {
    feature_image_src:             "/static/images/mit-dome.png",
    page_url:                      "/courses/course-v1:edX+E2E-101/",
    financial_assistance_form_url: "",
    description:                   "E2E Test Course",
    current_price:                 999.0,
    instructors:                   [],
    live:                          true
  }
}

const displayedProgram = {
  title:        "P2",
  readable_id:  "P2",
  id:           2,
  requirements: {
    required:  [1],
    electives: []
  },
  courses:  [1],
  req_tree: [
    {
      data: {
        node_type:      "program_root",
        operator:       null,
        operator_value: null,
        program:        2,
        course:         null,
        title:          "",
        elective_flag:  false
      },
      id:       4,
      children: [
        {
          data: {
            node_type:      "operator",
            operator:       "all_of",
            operator_value: null,
            program:        2,
            course:         null,
            title:          "Required Courses",
            elective_flag:  false
          },
          id:       5,
          children: [
            {
              data: {
                node_type:      "course",
                operator:       null,
                operator_value: null,
                program:        2,
                course:         1,
                title:          null,
                elective_flag:  false
              },
              id: 6
            }
          ]
        }
      ]
    }
  ],
  page: {
    feature_image_src:
      "http://mitxonline.odl.local:8013/static/images/mit-dome.png"
  },
  program_type: "Series",
  departments:  [
    {
      name: "Science"
    }
  ],
  live: true
}

describe("CatalogPage", function() {
  const mockIntersectionObserver = class {
    constructor() {}
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  let helper, courses, programs, renderPage

  this.timeout(50000)

  beforeEach(() => {
    // Mock the intersection observer.
    helper = new IntegrationTestHelper()
    window.IntersectionObserver = mockIntersectionObserver

    renderPage = helper.configureShallowRenderer(CatalogPage, InnerCatalogPage)

    SETTINGS.features = {
      "mitxonline-new-product-page": true
    }
  })

  afterEach(() => {
    helper.cleanup()
  })

  it("default state is set when catalog renders", async () => {
    courses = [displayedCourse]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses
          },
          departments: [
            {
              name:        "History",
              slug:        "history",
              course_ids:  [1],
              program_ids: [1]
            },
            {
              name:        "Science",
              slug:        "science",
              course_ids:  [1],
              program_ids: [1]
            }
          ]
        }
      },
      {}
    )

    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    inner.instance().componentDidUpdate({}, {})
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
  })

  it("updates state from changeSelectedTab when selecting program tab", async () => {
    courses = [displayedCourse]
    programs = Array(5).fill(displayedProgram)
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses
          },
          programs: {
            count:   5,
            results: programs
          },
          departments: [
            {
              name:        "History",
              slug:        "history",
              course_ids:  [],
              program_ids: [1, 2, 3, 4, 5]
            },
            {
              name:        "Science",
              slug:        "science",
              course_ids:  [2],
              program_ids: []
            }
          ]
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    inner.instance().changeSelectedTab("programs")
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("programs")
    expect(JSON.stringify(inner.state().filteredPrograms)).equals(
      JSON.stringify(programs)
    )
    expect(JSON.stringify(inner.state().allProgramsRetrieved)).equals(
      JSON.stringify(programs)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(5)
  })

  it("renders catalog department filter for courses and programs tabs", async () => {
    const allDepartments = {
      name: "All Departments",
      slug: "All Departments"
    }
    const department1 = {
      name:        "department1",
      slug:        "department1",
      course_ids:  [1],
      program_ids: []
    }
    const department2 = {
      name:        "department2",
      slug:        "department2",
      course_ids:  [1],
      program_ids: [1]
    }
    const department3 = {
      name:        "department3",
      slug:        "department3",
      course_ids:  [],
      program_ids: [1]
    }
    const department4 = {
      name:        "department4",
      slug:        "department4",
      course_ids:  [],
      program_ids: []
    }
    const { inner } = await renderPage(
      {
        queries: {
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          departments: [department1, department2, department3, department4]
        }
      },
      {}
    )
    let filteredDepartments = inner
      .instance()
      .filterDepartmentsByTabName("courses")
    expect(JSON.stringify(filteredDepartments)).equals(
      JSON.stringify([allDepartments, department1, department2])
    )
    filteredDepartments = inner
      .instance()
      .filterDepartmentsByTabName("programs")
    expect(JSON.stringify(filteredDepartments)).equals(
      JSON.stringify([allDepartments, department2, department3])
    )
  })

  it("renders catalog courses when filtered by department", async () => {
    const course1 = JSON.parse(JSON.stringify(displayedCourse))
    course1.departments = [{ name: "Math" }]
    course1.id = 1
    const course2 = JSON.parse(JSON.stringify(displayedCourse))
    course2.departments = [{ name: "Science" }]
    course2.id = 2
    const course3 = JSON.parse(JSON.stringify(displayedCourse))
    course3.departments = [{ name: "Science" }]
    course3.id = 3
    courses = [course1, course2, course3]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   3,
            results: courses
          },
          programs: {
            results: [displayedProgram]
          },
          departments: [
            {
              name:        "Science",
              slug:        "science",
              course_ids:  [1, 3],
              program_ids: [2, 3]
            },
            {
              name:        "Math",
              slug:        "math",
              course_ids:  [1],
              program_ids: [1]
            },
            {
              name:        "department4",
              slug:        "department4",
              course_ids:  [],
              program_ids: []
            }
          ]
        }
      },
      {}
    )
    inner.state().tabSelected = "courses"
    inner.state().selectedDepartment = "math"
    let coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesOrProgramsByDepartmentSlug("math", courses, "courses")
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(1)
    inner.state().selectedDepartment = "science"
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesOrProgramsByDepartmentSlug("science", courses, "courses")
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(2)
    inner.state().selectedDepartment = "All Departments"
    coursesFilteredByCriteriaAndDepartment = inner
      .instance()
      .filteredCoursesOrProgramsByDepartmentSlug(
        "All Departments",
        courses,
        "courses"
      )
    expect(coursesFilteredByCriteriaAndDepartment.length).equals(3)
  })

  it("renders catalog programs when filtered by department", async () => {
    const program1 = JSON.parse(JSON.stringify(displayedProgram))
    program1.departments = ["Math"]
    program1.id = 1
    const program2 = JSON.parse(JSON.stringify(displayedProgram))
    program2.departments = ["History"]
    program2.id = 2
    const program3 = JSON.parse(JSON.stringify(displayedProgram))
    program3.departments = ["History"]
    program3.id = 3
    programs = [program1, program2, program3]
    const { inner } = await renderPage({
      queries: {
        programs: {
          isPending: false,
          status:    200
        },
        departments: {
          isPending: false,
          status:    200
        }
      },
      entities: {
        programs: {
          count:   3,
          results: [program1, program2, program3]
        },
        departments: [
          {
            name:        "History",
            slug:        "history",
            course_ids:  [1, 2],
            program_ids: [2, 3]
          },
          {
            name:        "Math",
            slug:        "math",
            course_ids:  [1, 2, 3],
            program_ids: [1]
          },
          {
            name:        "department4",
            slug:        "department4",
            course_ids:  [],
            program_ids: []
          }
        ]
      }
    })
    inner.state().tabSelected = "programs"
    inner.state().selectedDepartment = "math"
    let programsFilteredByDepartment = inner
      .instance()
      .filteredCoursesOrProgramsByDepartmentSlug("math", programs, "programs")
    expect(programsFilteredByDepartment.length).equals(1)
    inner.state().selectedDepartment = "history"
    programsFilteredByDepartment = inner
      .instance()
      .filteredCoursesOrProgramsByDepartmentSlug(
        "history",
        programs,
        "programs"
      )
    expect(programsFilteredByDepartment.length).equals(2)
    inner.state().selectedDepartment = "All Departments"
    programsFilteredByDepartment = inner
      .instance()
      .filteredCoursesOrProgramsByDepartmentSlug(
        "All Departments",
        programs,
        "programs"
      )
    expect(programsFilteredByDepartment.length).equals(3)
  })

  it("renders catalog courses based on selected department", async () => {
    const course1 = JSON.parse(JSON.stringify(displayedCourse))
    course1.departments = [{ name: "Math" }]
    course1.id = 1
    const course2 = JSON.parse(JSON.stringify(displayedCourse))
    course2.departments = [{ name: "Math" }, { name: "History" }]
    course2.id = 2
    const course3 = JSON.parse(JSON.stringify(displayedCourse))
    course3.departments = [{ name: "Math" }, { name: "History" }]
    course3.id = 3
    courses = [course1, course2, course3]
    const program1 = JSON.parse(JSON.stringify(displayedProgram))
    program1.departments = [{ name: "History" }]
    program1.id = 1
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   3,
            results: courses
          },
          programs: {
            results: [program1]
          },
          departments: [
            {
              name:        "History",
              slug:        "history",
              course_ids:  [2, 3],
              program_ids: [1]
            },
            {
              name:        "Math",
              slug:        "math",
              course_ids:  [1, 2, 3],
              program_ids: []
            },
            {
              name:        "department4",
              slug:        "department4",
              course_ids:  [],
              program_ids: []
            }
          ]
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    // Default selected department is All Departments.
    expect(inner.state().selectedDepartment).equals("All Departments")
    // Default tab selected is courses.
    expect(inner.state().tabSelected).equals("courses")
    // All of the courses should be visible.
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    // Number of catalog items should match the number of visible courses.
    expect(inner.instance().renderNumberOfCatalogItems()).equals(3)

    // Select a department to filter by.
    inner.instance().changeSelectedDepartment("history")
    // Confirm the state updated to reflect the selected department.
    expect(inner.state().selectedDepartment).equals("history")
    expect(inner.state().tabSelected).equals("courses")
    // Confirm the number of catalog items updated to reflect the items filtered by department.
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
    // Confirm the courses filtered are those which have a department name matching the selected department.
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify([course2, course3])
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )

    // Change to the programs tab.
    inner.instance().changeSelectedTab("programs")
    expect(inner.state().tabSelected).equals("programs")
    // Confirm that the selected department is the same as before.
    expect(inner.state().selectedDepartment).equals("history")

    // Change back to the courses tab.
    inner.instance().changeSelectedTab("courses")
    // Confirm the courses filtered are those which have a department name matching the selected department.
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify([course2, course3])
    )
  })

  it("load more at the bottom of the courses catalog page, all departments filter", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   2,
            results: courses,
            next:    "http://fake.com/api/courses/?page=2"
          },
          programs: {
            count:   2,
            results: programs
          }
        }
      },
      {}
    )

    expect(inner.state().courseQueryPage).equals(1)
    inner.instance().componentDidUpdate({}, {})
    inner.state().courseQueryPage = 2
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    // one shows visually, but the total is 2
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
    const course2 = JSON.parse(JSON.stringify(displayedCourse))
    course2.id = 3
    course2.departments = [{ name: "Math" }, { name: "History" }]

    // Mock the second page of course API results.
    helper.handleRequestStub.returns({
      body: {
        next:    null,
        results: [course2]
      }
    })
    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]

    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    sinon.assert.calledWith(
      helper.handleRequestStub,
      "/api/v2/courses/?page=2&live=true&page__live=true&courserun_is_enrollable=true",
      "GET"
    )

    // Should expect 2 courses to be visually displayed in the catalog now. Total count should stay 2.
    expect(inner.state().courseQueryPage).equals(2)
    expect(inner.instance().renderNumberOfCatalogItems()).equals(2)
  })

  it("do not load more at the bottom of the courses catalog page if next page is null", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses,
            next:    null
          },
          programs: {
            count:   1,
            results: programs
          }
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
    expect(inner.state().courseQueryPage).equals(1)

    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]
    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    // Should not expect any additional courses.
    expect(inner.state().courseQueryPage).equals(1)
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
  })

  it("do not load more at the bottom of the courses catalog page if isLoadingMoreItems is true", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses,
            next:    "http://fake.com/api/courses/?page=2"
          },
          programs: {
            count:   1,
            results: programs
          }
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("courses")
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
    expect(inner.state().courseQueryPage).equals(1)

    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]

    // Set isLoadingMoreItems to true which simualtes that the next page
    // request is already in progress.
    inner.state().isLoadingMoreItems = true
    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    // Should not expect any additional courses.
    expect(inner.state().courseQueryPage).equals(1)
    expect(JSON.stringify(inner.state().allCoursesRetrieved)).equals(
      JSON.stringify(courses)
    )
    expect(JSON.stringify(inner.state().filteredCourses)).equals(
      JSON.stringify(courses)
    )
    expect(inner.instance().renderNumberOfCatalogItems()).equals(1)
  })

  it("load more at the bottom of the programs catalog page, all departments filter", async () => {
    courses = [displayedCourse]
    programs = [displayedProgram]
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: courses,
            next:    "http://fake.com/api/courses/?page=2"
          },
          programs: {
            count:   4,
            results: programs,
            next:    "http://fake.com/api/courses/?page=2"
          },
          departments: [
            {
              name:        "History",
              course_ids:  [1],
              program_ids: [1]
            }
          ]
        }
      },
      {}
    )
    inner.instance().componentDidUpdate({}, {})
    expect(inner.state().allProgramsRetrieved.length).equals(1)
    expect(inner.state().filteredPrograms.length).equals(1)
    inner.instance().changeSelectedTab("programs")
    expect(inner.state().selectedDepartment).equals("All Departments")
    expect(inner.state().tabSelected).equals("programs")
    expect(JSON.stringify(inner.state().filteredPrograms)).equals(
      JSON.stringify(programs)
    )
    expect(JSON.stringify(inner.state().allProgramsRetrieved)).equals(
      JSON.stringify(programs)
    )
    // While there is only one showing, there are still 4 total per the count. The total should be shown.
    expect(inner.instance().renderNumberOfCatalogItems()).equals(4)

    // simulate the state variables changing correctly since the shallow render doesn't actually change the state
    inner.state().programQueryPage = 2
    inner.state().isLoadingMoreItems = false

    // Simulate the user reaching the bottom of the catalog page.
    const entry = [{ isIntersecting: true }]
    await inner.instance().bottomOfLoadedCatalogCallback(entry)

    sinon.assert.calledWith(
      helper.handleRequestStub,
      "/api/v2/programs/?page=2&live=true&page__live=true",
      "GET"
    )

    // The count should still be 4 regardless of how many are added or not, since the highest provided count was 4.
    expect(inner.instance().renderNumberOfCatalogItems()).equals(4)
  })

  it("mergeCourseOrProgramArrays removes duplicates if present", async () => {
    const oldArray = [displayedProgram]
    const newArray = [displayedProgram]
    const { inner } = await renderPage()
    const mergedArray = inner
      .instance()
      .mergeCourseOrProgramArrays(oldArray, newArray)
    expect(mergedArray.length).equals(1)
    expect(JSON.stringify(mergedArray)).equals(JSON.stringify(oldArray))
  })

  it("mergeCourseOrProgramArrays merges objects if they are not duplicates", async () => {
    const oldArray = [displayedProgram]
    const newProgram = JSON.parse(JSON.stringify(displayedProgram))
    newProgram.id = 3
    const newArray = [newProgram]
    const { inner } = await renderPage()
    const mergedArray = inner
      .instance()
      .mergeCourseOrProgramArrays(oldArray, newArray)
    expect(mergedArray.length).equals(2)
    expect(JSON.stringify(mergedArray)).equals(
      JSON.stringify([displayedProgram, newProgram])
    )
  })

  it("mergeCourseOrProgramArrays keeps items with different IDs and removes duplicates", async () => {
    const oldArray = [displayedProgram]
    const newProgram = JSON.parse(JSON.stringify(displayedProgram))
    newProgram.id = 3
    const newArray = [newProgram, displayedProgram, displayedProgram]
    const { inner } = await renderPage()
    const mergedArray = inner
      .instance()
      .mergeCourseOrProgramArrays(oldArray, newArray)
    expect(mergedArray.length).equals(2)
    expect(JSON.stringify(mergedArray)).equals(
      JSON.stringify([displayedProgram, newProgram])
    )
  })

  it("renderCatalogCount is plural for more than one course", async () => {
    const displayedProgram2 = JSON.parse(JSON.stringify(displayedProgram))
    displayedProgram2.id = 2
    const displayedCourse2 = JSON.parse(JSON.stringify(displayedCourse))
    displayedCourse2.id = 2
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   2,
            results: [displayedCourse, displayedCourse2]
          },
          programs: {
            count:   2,
            results: [displayedProgram, displayedProgram2]
          },
          departments: [
            {
              name:        "History",
              slug:        "history",
              course_ids:  [1],
              program_ids: [1]
            }
          ]
        }
      },
      {}
    )
    inner.setState({ tabSelected: "courses" })
    inner.setState({ selectedDepartment: "All Departments" })
    inner.setState({ allCoursesCount: 2 })
    expect(inner.find("h2.catalog-count").text()).equals("2 courses")
  })

  it("renderCatalogCount is plural for more than one program", async () => {
    const displayedProgram2 = JSON.parse(JSON.stringify(displayedProgram))
    displayedProgram2.id = 2
    const displayedCourse2 = JSON.parse(JSON.stringify(displayedCourse))
    displayedCourse2.id = 2
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   2,
            results: [displayedCourse, displayedCourse2]
          },
          programs: {
            count:   2,
            results: [displayedProgram, displayedProgram2]
          },
          departments: [
            {
              name:        "History",
              slug:        "history",
              course_ids:  [1],
              program_ids: [1]
            }
          ]
        }
      },
      {}
    )
    inner.setState({ tabSelected: "programs" })
    inner.setState({ selectedDepartment: "All Departments" })
    inner.setState({ allProgramsCount: 2 })
    expect(inner.find("h2.catalog-count").text()).equals("2 programs")
  })

  it("renderCatalogCount is singular for one course", async () => {
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: [displayedCourse]
          },
          programs: {
            count:   1,
            results: [displayedProgram]
          },
          departments: [
            {
              name:        "History",
              slug:        "history",
              course_ids:  [1],
              program_ids: [1]
            }
          ]
        }
      },
      {}
    )
    inner.setState({ tabSelected: "courses" })
    inner.setState({ selectedDepartment: "All Departments" })
    inner.setState({ allCoursesCount: 1 })
    expect(inner.find("h2.catalog-count").text()).equals("1 course")
  })

  it("renderCatalogCount is singular for one program", async () => {
    const { inner } = await renderPage(
      {
        queries: {
          courses: {
            isPending: false,
            status:    200
          },
          programs: {
            isPending: false,
            status:    200
          },
          departments: {
            isPending: false,
            status:    200
          }
        },
        entities: {
          courses: {
            count:   1,
            results: [displayedCourse]
          },
          programs: {
            count:   1,
            results: [displayedProgram]
          },
          departments: [
            {
              name:        "History",
              slug:        "history",
              course_ids:  [1],
              program_ids: [1]
            }
          ]
        }
      },
      {}
    )
    inner.setState({ tabSelected: "programs" })
    inner.setState({ selectedDepartment: "All Departments" })
    inner.setState({ allProgramsCount: 1 })
    inner.instance().componentDidUpdate({}, {})
    expect(inner.find("h2.catalog-count").text()).equals("1 program")
  })
})
