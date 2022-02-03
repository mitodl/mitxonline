import { makeUser } from "../../factories/user"
import { currentUserSelector } from "./users"

describe("users reducers", () => {
  describe("currentUserSelector", () => {
    it("should return the user context", () => {
      const currentUser = makeUser()
      expect(
        currentUserSelector({
          entities: {
            currentUser
          }
        })
      ).toEqual(currentUser)
    })
  })
})
