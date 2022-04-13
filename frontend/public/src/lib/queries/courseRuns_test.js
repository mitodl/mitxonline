// @flow
import { assert } from "chai"

import { courseRunsSelector } from "./courseRuns"

describe("courseRuns reducers", () => {
  describe("courseRunsSelector", () => {
    it("should return the courseRuns state", () => {
      const courseRuns = {
        key: "value"
      }
      assert.equal(courseRunsSelector({ entities: { courseRuns } }), courseRuns)
    })
  })
})
